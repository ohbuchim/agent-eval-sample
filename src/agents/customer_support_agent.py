"""Customer support agent with knowledge base search capability."""

from pathlib import Path

from strands import Agent

from src.tools.knowledge_search import search_knowledge_base, set_knowledge_directory

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

## 回答のフォーマット
- 簡潔で分かりやすい文章で回答してください
- 必要に応じて箇条書きを使用してください
- 具体的な手順がある場合は、ステップバイステップで説明してください
"""


def create_customer_support_agent(
    knowledge_dir: Path | str | None = None,
    callback_handler: object | None = None,
) -> Agent:
    """Create a customer support agent with knowledge base search capability.

    Args:
        knowledge_dir: Path to the knowledge directory. If None, uses default.
        callback_handler: Optional callback handler for streaming output.
            Pass None to disable console output.

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

    # Create agent with knowledge search tool
    agent = Agent(
        system_prompt=CUSTOMER_SUPPORT_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
        callback_handler=callback_handler,
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
