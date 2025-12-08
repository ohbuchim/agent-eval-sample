"""Customer support agent with knowledge base search capability."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands import Agent
from strands.hooks import (
    AfterToolCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from src.models import ModelType, create_bedrock_model
from src.tools.knowledge_search import search_knowledge_base, set_knowledge_directory


class ProgressCallbackHandler:
    """Callback handler that shows progress indicators during agent processing."""

    def __init__(self) -> None:
        """Initialize the callback handler."""
        self._is_thinking = False
        self._current_tool: str | None = None
        self._text_started = False

    def _clear_status(self) -> None:
        """Clear the current status line."""
        # Move cursor to beginning and clear line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def _show_status(self, message: str) -> None:
        """Show a status message on the current line."""
        self._clear_status()
        sys.stdout.write(f"\r⏳ {message}")
        sys.stdout.flush()

    def __call__(self, **kwargs) -> None:
        """Handle callback events from the agent.

        Args:
            **kwargs: Event data from the agent.
        """
        # Event loop started - show thinking indicator
        if kwargs.get("init_event_loop", False):
            self._is_thinking = True
            self._text_started = False
            self._show_status("回答を準備しております...")

        # Tool usage started
        if "current_tool_use" in kwargs:
            tool_use = kwargs["current_tool_use"]
            tool_name = tool_use.get("name")
            if tool_name and tool_name != self._current_tool:
                self._current_tool = tool_name
                self._show_status("関連情報を確認しております...")

        # Text generation started - clear status and print text
        if "data" in kwargs:
            if self._is_thinking or self._current_tool:
                self._clear_status()
                self._is_thinking = False
                self._current_tool = None
            # Print the streaming text
            sys.stdout.write(kwargs["data"])
            sys.stdout.flush()
            self._text_started = True

        # Event loop completed
        if kwargs.get("complete", False):
            if self._is_thinking or self._current_tool:
                self._clear_status()
            self._is_thinking = False
            self._current_tool = None
            if self._text_started:
                # Add newline after streamed output
                sys.stdout.write("\n")
                sys.stdout.flush()


class ToolUsageTracker(HookProvider):
    """Hook provider that tracks tool usage during agent execution.

    This class captures tool names, inputs, and outputs for each tool invocation
    during agent execution. The collected data can be retrieved and cleared
    using the get_and_clear() method.
    """

    def __init__(self) -> None:
        """Initialize the tool usage tracker."""
        self._pending: dict[str, dict[str, Any]] = {}  # toolUseId -> {name, input}
        self._tool_uses: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register hook callbacks for tool events.

        Args:
            registry: The hook registry to register callbacks with.
        """
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool)

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Capture tool name and input before execution.

        Args:
            event: The before tool call event.
        """
        tool_use_id = event.tool_use.get("toolUseId", "")
        self._pending[tool_use_id] = {
            "name": event.tool_use.get("name", ""),
            "input": event.tool_use.get("input", {}),
        }

    def _on_after_tool(self, event: AfterToolCallEvent) -> None:
        """Capture tool output after execution.

        Args:
            event: The after tool call event.
        """
        tool_use_id = event.tool_use.get("toolUseId", "")
        if tool_use_id in self._pending:
            pending = self._pending.pop(tool_use_id)
            output = ""
            if event.result and "content" in event.result:
                for block in event.result["content"]:
                    if "text" in block:
                        output = block["text"]
                        break
            self._tool_uses.append(
                {
                    "tool_name": pending["name"],
                    "tool_input": pending["input"],
                    "tool_output": output,
                }
            )

    def get_and_clear(self) -> list[dict[str, Any]]:
        """Get all recorded tool uses and clear the internal state.

        Returns:
            List of dictionaries containing tool_name, tool_input, and tool_output.
        """
        result = self._tool_uses.copy()
        self._tool_uses = []
        self._pending = {}
        return result


# System prompt for the customer support agent
CUSTOMER_SUPPORT_SYSTEM_PROMPT = """あなたは親切で丁寧なカスタマーサポート担当者です。

## 役割
お客様からの問い合わせに対して、ナレッジベースを検索し、正確で役立つ情報を提供します。

## 行動指針
1. まずお客様の質問を理解し、適切なキーワードでナレッジベースを検索してください
2. 検索結果に基づいて、明確で分かりやすい回答を提供してください
3. 検索結果に該当する情報がない場合は、正直にその旨を伝え、
   カスタマーサポートへの直接連絡を案内してください
4. 常に敬語を使用し、お客様に寄り添った対応を心がけてください

## 条件分岐がある場合の対応（重要）
検索結果に条件によって異なる対応が含まれている場合（例：個人/法人、保証期間内/外、購入日数など）：

1. **すべての条件を一度に説明しないでください**
2. まず、お客様がどの条件に該当するかを特定するための質問をしてください
   - 例：「個人のお客様でしょうか、法人のお客様でしょうか？」
   - 例：「ご購入からどれくらい経過されていますか？」
   - 例：「製品は未開封の状態でしょうか？」
3. お客様の回答を受けてから、**該当する条件の情報のみ**をピンポイントで回答してください
4. 該当しない条件の情報は提供しないでください

### 条件確認の例
❌ 悪い例：「個人の場合は〇〇、法人の場合は△△です」（すべて列挙）
✅ 良い例：「個人のお客様でしょうか、法人のお客様でしょうか？」
   → 回答を受けて該当部分のみ説明

## 回答のフォーマット
- 簡潔で分かりやすい文章で回答してください
- 必要に応じて箇条書きを使用してください
- 具体的な手順がある場合は、ステップバイステップで説明してください
"""


def create_customer_support_agent(
    knowledge_dir: Path | str | None = None,
    callback_handler: Callable[..., Any] | None = None,
    tool_tracker: ToolUsageTracker | None = None,
) -> Agent:
    """Create a customer support agent with knowledge base search capability.

    Args:
        knowledge_dir: Path to the knowledge directory. If None, uses default.
        callback_handler: Optional callback handler for streaming output.
            Pass None to disable console output.
        tool_tracker: Optional ToolUsageTracker to capture tool usage information.

    Returns:
        Configured customer support agent.
    """
    # Set knowledge directory
    if knowledge_dir is not None:
        set_knowledge_directory(knowledge_dir)
    else:
        # Default to 'knowledge' directory relative to project root
        project_root = Path(__file__).parent.parent.parent
        set_knowledge_directory(project_root / "knowledge")

    # Create Bedrock model with Claude Sonnet 4.5 (global inference)
    model = create_bedrock_model(ModelType.SONNET)

    # Set up hooks for tool tracking
    hooks: list[HookProvider] = [tool_tracker] if tool_tracker else []

    # Create agent with knowledge search tool
    agent = Agent(
        model=model,
        system_prompt=CUSTOMER_SUPPORT_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
        callback_handler=callback_handler,
        hooks=hooks,
    )

    return agent


def get_customer_support_response(agent: Agent, user_message: str) -> str:
    """Get a response from the customer support agent.

    Args:
        agent: The customer support agent instance.
        user_message: The user's message/question.

    Returns:
        The agent's response as a string.
    """
    result = agent(user_message)
    return str(result)


if __name__ == "__main__":
    print("カスタマーサポートエージェントを起動しています...")
    # Use ProgressCallbackHandler to show status during processing
    agent = create_customer_support_agent(callback_handler=ProgressCallbackHandler())
    print("起動完了。質問を入力してください（終了: quit）\n")

    while True:
        try:
            user_input = input("あなた: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("終了します。")
                break
            if not user_input:
                continue
            print("\nサポート: ", end="", flush=True)
            # Response is already streamed by callback handler
            agent(user_input)
            print()
        except KeyboardInterrupt:
            print("\n終了します。")
            break
