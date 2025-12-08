"""Evaluation logic for customer support agent using simulated users."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from strands import Agent

from src.agents.customer_support_agent import (
    ToolUsageTracker,
    create_customer_support_agent,
    get_customer_support_response,
)
from src.agents.simulated_user_agent import (
    UserPersona,
    UserScenario,
    create_simulated_user_agent,
)
from src.evaluation.scenarios import (
    EVALUATION_SCENARIOS,
    EvaluationScenario,
    load_scenarios_from_json,
)
from src.models import ModelType, get_shared_model

logger = logging.getLogger(__name__)

# Evaluation constants
PASS_THRESHOLD = 0.7
PARTIAL_THRESHOLD = 0.4

# LLM evaluation score range
MIN_LLM_SCORE = 1
MAX_LLM_SCORE = 5
DEFAULT_LLM_SCORE = 3


@dataclass
class ToolUsage:
    """Record of a single tool usage during agent response.

    Attributes:
        tool_name: Name of the tool (e.g., "search_knowledge_base").
        tool_input: Dictionary of input parameters passed to the tool.
        tool_output: The string output returned by the tool.
    """

    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str


@dataclass
class ConversationTurn:
    """A single turn in the conversation.

    Attributes:
        role: Either "user" or "support".
        message: The message content.
        turn_number: The turn number in the conversation.
        tool_uses: List of tool usages during this turn (support turns only).
    """

    role: str
    message: str
    turn_number: int = 0
    tool_uses: list[ToolUsage] = field(default_factory=list)


@dataclass
class ConversationResult:
    """Result of a simulated conversation.

    Attributes:
        scenario_name: Name of the evaluation scenario.
        turns: List of conversation turns.
        completed: Whether the conversation completed successfully.
        natural_end: Whether the conversation ended naturally (user thanked).
        error: Error message if any.
    """

    scenario_name: str
    turns: list[ConversationTurn] = field(default_factory=list)
    completed: bool = False
    natural_end: bool = False
    error: str | None = None


@dataclass
class LLMEvaluation:
    """LLM-based evaluation result for a scenario.

    Attributes:
        score: Score from 1 (completely failed) to 5 (perfectly answered).
        comment: Detailed evaluation comment.
    """

    score: int
    comment: str


@dataclass
class EvaluationResult:
    """Result of evaluating a single scenario.

    Attributes:
        scenario: The evaluation scenario.
        conversation: The conversation result.
        topics_covered: List of expected topics that were covered.
        topics_missing: List of expected topics that were not covered.
        score: Overall score (0.0 to 1.0).
        turn_count: Number of conversation turns.
        llm_evaluation: LLM-based evaluation with score and comment.
    """

    scenario: EvaluationScenario
    conversation: ConversationResult
    topics_covered: list[str] = field(default_factory=list)
    topics_missing: list[str] = field(default_factory=list)
    score: float = 0.0
    turn_count: int = 0
    llm_evaluation: LLMEvaluation | None = None


def _create_analysis_agent(system_prompt: str) -> Agent:
    """Create an agent for analysis tasks.

    Uses the shared Haiku 4.5 model for efficient resource usage.

    Args:
        system_prompt: System prompt for the analysis agent.

    Returns:
        Configured agent for analysis.
    """
    model = get_shared_model(ModelType.HAIKU)
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[],
        callback_handler=None,
    )


def _invoke_agent_with_retry(
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 3,
    base_wait_time: float = 1.0,
) -> str:
    """Invoke an analysis agent with retry logic.

    Creates an agent and invokes it with exponential backoff retry on failure.

    Args:
        system_prompt: System prompt for the agent.
        user_prompt: User prompt to send to the agent.
        max_retries: Maximum number of retry attempts.
        base_wait_time: Initial wait time in seconds for exponential backoff.

    Returns:
        The agent's response as a string.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    agent = _create_analysis_agent(system_prompt)

    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            result = str(agent(user_prompt))
            if attempt > 0:
                logger.info(
                    f"Agent invocation succeeded on attempt {attempt + 1}/{max_retries}"
                )
            return result
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = base_wait_time * (2**attempt)
                logger.warning(
                    f"Agent invocation failed (attempt {attempt + 1}/{max_retries}): "
                    f"{e}. Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
            else:
                logger.warning(
                    f"Agent invocation failed after {max_retries} attempts: {e}"
                )

    raise RuntimeError(f"All {max_retries} retry attempts failed") from last_exception


def analyze_conversation_end_intent(user_message: str) -> bool:
    """Analyze if the user message indicates intent to end the conversation.

    Uses Haiku 4.5 global inference to determine if the user's message
    signals that they want to end the conversation (e.g., thanking and
    saying goodbye) versus continuing with follow-up questions.

    Args:
        user_message: The user's message to analyze.

    Returns:
        True if the user intends to end the conversation, False otherwise.
    """
    analysis_prompt = (
        f"""以下のカスタマーサポートへのユーザーメッセージを"""
        f"""分析してください。

ユーザーメッセージ:
\"\"\"
{user_message}
\"\"\"

このメッセージは「会話を終了したい意図」を示していますか？

## 判定基準

### 終了の意図がある場合 (END):
- 感謝を述べて質問がない
- 「以上です」「問題解決しました」などの明確な終了表現
- 「ありがとうございました」で締めくくり、追加質問がない

### 終了の意図がない場合 (CONTINUE):
- 感謝を述べつつも追加の質問をしている
- 確認や詳細を求めている
- 「ありがとうございます」の後に「ですが」「ところで」などで続いている
- 疑問符（？）を含む質問がある

## 回答形式
必ず以下のいずれか一つだけを回答してください:
END
または
CONTINUE
"""
    )

    system_prompt = "あなたは会話分析の専門家です。指示に従って正確に判定してください。"

    try:
        result = _invoke_agent_with_retry(system_prompt, analysis_prompt)
        result = result.strip().upper()
        # Check if the result contains END
        return "END" in result and "CONTINUE" not in result
    except RuntimeError:
        # If all retries fail, default to not ending (safer to continue)
        return False


def generate_llm_evaluation(
    scenario: "EvaluationScenario",
    conversation: ConversationResult,
) -> LLMEvaluation:
    """Generate LLM-based evaluation for a scenario conversation.

    Uses Haiku 4.5 global inference to analyze the conversation and generate
    a comprehensive evaluation with score (1-5) and detailed comment.

    Args:
        scenario: The evaluation scenario.
        conversation: The conversation result.

    Returns:
        LLMEvaluation with score and comment.
    """

    # Build conversation history text
    conversation_text = ""
    for turn in conversation.turns:
        role_label = "ユーザー" if turn.role == "user" else "サポート"
        conversation_text += f"\n【{role_label}】(ターン {turn.turn_number})\n"
        conversation_text += f"{turn.message}\n"

    evaluation_prompt = f"""以下のカスタマーサポートの会話を評価してください。

## シナリオ情報
- シナリオ名: {scenario.name}
- 説明: {scenario.description}
- ユーザーの目的: {scenario.user_goal or scenario.description}
- ユーザーの状況: {scenario.user_context or "特になし"}
- ユーザーのペルソナ: {scenario.persona}
- 期待されるトピック: {", ".join(scenario.expected_topics)}

## 会話履歴
{conversation_text}

## 評価基準

以下の観点から総合的に評価してください：

1. **目的達成度**: ユーザーの質問・目的に対して適切に回答できたか
2. **情報の正確性**: 提供した情報は正確で具体的だったか
3. **対応の適切さ**: ユーザーのペルソナ（{scenario.persona}）に合った対応だったか
4. **会話の自然さ**: 会話が自然に進行し、適切に終了したか
5. **トピックカバー**: 期待されるトピック（{
        ", ".join(scenario.expected_topics)
    }）がカバーされたか

## スコア基準

- **5点**: ユーザーの質問に完全に回答し、満足のいく結果が得られた
- **4点**: ほぼ完全に回答したが、軽微な改善点がある
- **3点**: 部分的に回答したが、重要な情報が不足している
- **2点**: 回答が不十分で、ユーザーの目的を達成できていない
- **1点**: 全くユーザーの質問に回答できていない

## 出力形式

必ず以下の形式で出力してください：

SCORE: [1-5の数字]

COMMENT:
[評価コメント（2-4文程度で、良かった点と改善点を含める）]
"""

    system_prompt = (
        "あなたはカスタマーサポートの品質評価の専門家です。"
        "会話を客観的に分析し、具体的な評価を提供してください。"
    )

    try:
        result = _invoke_agent_with_retry(system_prompt, evaluation_prompt)

        # Parse score
        score = DEFAULT_LLM_SCORE
        if "SCORE:" in result:
            score_line = result.split("SCORE:")[1].split("\n")[0].strip()
            try:
                score = int(score_line)
                score = max(MIN_LLM_SCORE, min(MAX_LLM_SCORE, score))
            except ValueError:
                pass

        # Parse comment
        comment = "評価コメントを取得できませんでした。"
        if "COMMENT:" in result:
            comment = result.split("COMMENT:")[1].strip()

        return LLMEvaluation(score=score, comment=comment)

    except RuntimeError as e:
        logger.warning(f"Failed to generate LLM evaluation: {e}")
        return LLMEvaluation(
            score=3,
            comment=f"評価中にエラーが発生しました: {e}",
        )


def _get_persona_enum(persona_str: str) -> UserPersona:
    """Convert persona string to UserPersona enum.

    Args:
        persona_str: Persona string from scenario.

    Returns:
        Corresponding UserPersona enum value.
    """
    persona_map = {
        "polite": UserPersona.POLITE,
        "frustrated": UserPersona.FRUSTRATED,
        "confused": UserPersona.CONFUSED,
        "detailed": UserPersona.DETAILED,
        "curt": UserPersona.CURT,
    }
    return persona_map.get(persona_str.lower(), UserPersona.POLITE)


def _build_flow_aware_prompt(
    scenario: EvaluationScenario,
    current_turn: int,
    support_response: str,
) -> str:
    """Build a prompt for the simulated user that considers conversation flow.

    Args:
        scenario: The evaluation scenario.
        current_turn: Current turn number (1-indexed).
        support_response: The support agent's response.

    Returns:
        Prompt for the simulated user.
    """
    base_prompt = f"""カスタマーサポートからの回答:
{support_response}

上記の回答を受けて、あなたの役割に沿った自然な返答をしてください。
目的が達成されたと感じたら、感謝を述べて会話を終えてください。
"""

    # Add flow hints if conversation_flow is defined
    if scenario.conversation_flow:
        for step in scenario.conversation_flow:
            if step.turn == current_turn and step.user_response_hint:
                base_prompt += f"""

【参考】このターンでは以下のような内容を伝えることを想定しています:
「{step.user_response_hint}」
ただし、サポートの回答内容に応じて自然に調整してください。
"""
                break

    return base_prompt


def run_conversation(
    support_agent: Agent,
    scenario: EvaluationScenario,
    max_turns: int | None = None,
    tool_tracker: ToolUsageTracker | None = None,
) -> ConversationResult:
    """Run a simulated conversation between user and support agent.

    Args:
        support_agent: The customer support agent.
        scenario: The evaluation scenario.
        max_turns: Maximum number of total turns. If None, uses scenario's max_turns.
        tool_tracker: Optional ToolUsageTracker to capture tool usage information.

    Returns:
        The conversation result.
    """
    if max_turns is None:
        max_turns = scenario.max_turns

    result = ConversationResult(scenario_name=scenario.name)

    try:
        # Create user scenario from evaluation scenario
        user_scenario = UserScenario(
            persona=_get_persona_enum(scenario.persona),
            initial_query=scenario.initial_query,
            goal=scenario.user_goal or scenario.description,
            context=scenario.user_context,
            max_turns=max_turns,
        )

        # Create simulated user agent (disable console output)
        user_agent = create_simulated_user_agent(
            scenario=user_scenario,
            callback_handler=None,
        )

        # Start with the initial query
        user_message = scenario.initial_query
        turn_number = 1
        result.turns.append(
            ConversationTurn(role="user", message=user_message, turn_number=turn_number)
        )

        for turn in range(max_turns):
            # Clear tool tracker before each support response
            if tool_tracker:
                tool_tracker.get_and_clear()

            # Get support agent response
            support_response = get_customer_support_response(
                support_agent, user_message
            )

            # Capture tool uses for this turn
            turn_tool_uses: list[ToolUsage] = []
            if tool_tracker:
                for tu in tool_tracker.get_and_clear():
                    turn_tool_uses.append(
                        ToolUsage(
                            tool_name=tu["tool_name"],
                            tool_input=tu["tool_input"],
                            tool_output=tu["tool_output"],
                        )
                    )

            result.turns.append(
                ConversationTurn(
                    role="support",
                    message=support_response,
                    turn_number=turn_number,
                    tool_uses=turn_tool_uses,
                )
            )

            # Check if this is the last allowed turn
            if turn >= max_turns - 1:
                break

            # Build flow-aware prompt for simulated user
            turn_number += 1
            user_prompt = _build_flow_aware_prompt(
                scenario, turn_number, support_response
            )

            # Get simulated user response using custom prompt
            user_message = str(user_agent(user_prompt))
            result.turns.append(
                ConversationTurn(
                    role="user", message=user_message, turn_number=turn_number
                )
            )

            # Check if conversation ended naturally using LLM analysis
            if analyze_conversation_end_intent(user_message):
                result.natural_end = True
                result.completed = True
                break

        if not result.completed:
            result.completed = True  # Mark as completed even if max turns reached

    except Exception as e:
        result.error = str(e)

    return result


def evaluate_conversation(
    scenario: EvaluationScenario,
    conversation: ConversationResult,
    generate_llm_eval: bool = True,
) -> EvaluationResult:
    """Evaluate a conversation against expected criteria.

    Args:
        scenario: The evaluation scenario.
        conversation: The conversation result.
        generate_llm_eval: Whether to generate LLM-based evaluation.

    Returns:
        The evaluation result with scores.
    """
    result = EvaluationResult(
        scenario=scenario,
        conversation=conversation,
        turn_count=len([t for t in conversation.turns if t.role == "support"]),
    )

    if conversation.error:
        result.score = 0.0
        return result

    # Combine all support responses for analysis
    support_responses = " ".join(
        turn.message for turn in conversation.turns if turn.role == "support"
    )

    # Check which expected topics were covered
    for topic in scenario.expected_topics:
        if topic in support_responses:
            result.topics_covered.append(topic)
        else:
            result.topics_missing.append(topic)

    # Calculate score based on topic coverage
    if scenario.expected_topics:
        result.score = len(result.topics_covered) / len(scenario.expected_topics)
    else:
        result.score = 1.0 if conversation.completed else 0.0

    # Generate LLM-based evaluation
    if generate_llm_eval:
        result.llm_evaluation = generate_llm_evaluation(scenario, conversation)

    return result


def _evaluate_single_scenario(
    scenario: EvaluationScenario,
    knowledge_dir: Path | str | None,
    scenario_index: int,
    total_scenarios: int,
) -> tuple[int, EvaluationResult]:
    """Evaluate a single scenario (for parallel execution).

    Args:
        scenario: The evaluation scenario.
        knowledge_dir: Path to the knowledge directory.
        scenario_index: Index of this scenario in the list.
        total_scenarios: Total number of scenarios.

    Returns:
        Tuple of (scenario_index, evaluation_result).
    """
    # Create tool tracker for this scenario
    tool_tracker = ToolUsageTracker()

    # Create new agent for this thread
    support_agent = create_customer_support_agent(
        knowledge_dir=knowledge_dir,
        callback_handler=None,
        tool_tracker=tool_tracker,
    )

    # Run conversation
    conversation = run_conversation(
        support_agent=support_agent,
        scenario=scenario,
        tool_tracker=tool_tracker,
    )

    # Evaluate
    eval_result = evaluate_conversation(scenario, conversation)

    return (scenario_index, eval_result)


def _run_evaluation_parallel(
    scenarios: list[EvaluationScenario],
    knowledge_dir: Path | str | None,
    max_workers: int,
    rate_limit_delay: float,
    verbose: bool,
) -> list[EvaluationResult]:
    """Run scenarios evaluation in parallel.

    Args:
        scenarios: List of scenarios to evaluate.
        knowledge_dir: Path to the knowledge directory.
        max_workers: Maximum number of parallel workers.
        rate_limit_delay: Delay in seconds between starting new tasks.
        verbose: Whether to print progress.

    Returns:
        List of evaluation results in original order.
    """
    results: list[EvaluationResult | None] = [None] * len(scenarios)
    completed_count = 0

    if verbose:
        print(f"\n並列実行: {len(scenarios)} シナリオ (最大 {max_workers} ワーカー)")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, scenario in enumerate(scenarios):
            future = executor.submit(
                _evaluate_single_scenario,
                scenario,
                knowledge_dir,
                i,
                len(scenarios),
            )
            futures[future] = (i, scenario)

            # Rate limiting
            if i < len(scenarios) - 1 and rate_limit_delay > 0:
                time.sleep(rate_limit_delay)

        for future in as_completed(futures):
            scenario_index, scenario = futures[future]
            try:
                idx, result = future.result()
                results[idx] = result
                completed_count += 1

                if verbose:
                    status = "PASS" if result.score >= PASS_THRESHOLD else "FAIL"
                    print(
                        f"  [{completed_count}/{len(scenarios)}] "
                        f"{scenario.name}: {result.score:.0%} [{status}]"
                    )

            except Exception as e:
                completed_count += 1
                # Create error result
                results[scenario_index] = EvaluationResult(
                    scenario=scenario,
                    conversation=ConversationResult(
                        scenario_name=scenario.name,
                        error=str(e),
                    ),
                    score=0.0,
                )
                if verbose:
                    print(
                        f"  [{completed_count}/{len(scenarios)}] "
                        f"{scenario.name}: ERROR - {e}"
                    )

    return [r for r in results if r is not None]


def run_evaluation(
    knowledge_dir: Path | str | None = None,
    scenarios: list[EvaluationScenario] | None = None,
    scenarios_json: Path | str | None = None,
    verbose: bool = True,
    parallel: bool = False,
    max_workers: int = 3,
    rate_limit_delay: float = 1.0,
) -> list[EvaluationResult]:
    """Run evaluation for multiple scenarios.

    Args:
        knowledge_dir: Path to the knowledge directory.
        scenarios: List of scenarios to evaluate. If None, uses default scenarios.
        scenarios_json: Path to JSON file containing scenarios. Takes precedence over
            scenarios parameter if both are provided.
        verbose: Whether to print progress.
        parallel: Whether to run scenarios in parallel.
        max_workers: Maximum number of parallel workers (only used if parallel=True).
        rate_limit_delay: Delay in seconds between starting new tasks (only used if
            parallel=True).

    Returns:
        List of evaluation results.
    """
    # Load scenarios from JSON if provided
    if scenarios_json is not None:
        scenario_set = load_scenarios_from_json(scenarios_json)
        scenarios = scenario_set.scenarios
        if verbose:
            print(f"Loaded {len(scenarios)} scenarios from {scenarios_json}")
    elif scenarios is None:
        scenarios = EVALUATION_SCENARIOS

    # Use parallel execution if enabled
    if parallel:
        return _run_evaluation_parallel(
            scenarios=scenarios,
            knowledge_dir=knowledge_dir,
            max_workers=max_workers,
            rate_limit_delay=rate_limit_delay,
            verbose=verbose,
        )

    # Create tool tracker for sequential execution
    tool_tracker = ToolUsageTracker()

    # Create support agent (disable console output for evaluation)
    support_agent = create_customer_support_agent(
        knowledge_dir=knowledge_dir,
        callback_handler=None,
        tool_tracker=tool_tracker,
    )

    results: list[EvaluationResult] = []

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            print(f"\n[{i}/{len(scenarios)}] Evaluating: {scenario.description}")
            if scenario.conversation_flow:
                steps = len(scenario.conversation_flow)
                print(f"  (Multi-turn scenario with {steps} expected steps)")

        # Run conversation
        conversation = run_conversation(
            support_agent=support_agent,
            scenario=scenario,
            tool_tracker=tool_tracker,
        )

        # Evaluate
        eval_result = evaluate_conversation(scenario, conversation)
        results.append(eval_result)

        if verbose:
            print(f"  Score: {eval_result.score:.2%}")
            print(f"  Turns: {eval_result.turn_count}")
            if conversation.natural_end:
                print("  Conversation ended naturally")
            if eval_result.topics_missing:
                print(f"  Missing topics: {', '.join(eval_result.topics_missing)}")
            if eval_result.llm_evaluation:
                print(f"  LLM Score: {eval_result.llm_evaluation.score}/5")

    return results


def print_evaluation_summary(results: list[EvaluationResult]) -> None:
    """Print a summary of evaluation results.

    Args:
        results: List of evaluation results.
    """
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)

    total_score = sum(r.score for r in results) / len(results) if results else 0

    print(f"\nOverall Score: {total_score:.2%}")
    print(f"Total Scenarios: {len(results)}")

    passed = sum(1 for r in results if r.score >= PASS_THRESHOLD)
    print(f"Passed (>= {PASS_THRESHOLD:.0%}): {passed}/{len(results)}")

    # Calculate average turns
    avg_turns = sum(r.turn_count for r in results) / len(results) if results else 0
    print(f"Average Turns: {avg_turns:.1f}")

    # Count natural endings
    natural_ends = sum(1 for r in results if r.conversation.natural_end)
    print(f"Natural Endings: {natural_ends}/{len(results)}")

    # Calculate average LLM score
    llm_scores = [
        r.llm_evaluation.score for r in results if r.llm_evaluation is not None
    ]
    if llm_scores:
        avg_llm_score = sum(llm_scores) / len(llm_scores)
        print(f"Average LLM Score: {avg_llm_score:.1f}/5")

    print("\nDetailed Results:")
    print("-" * 60)

    for result in results:
        status = "PASS" if result.score >= PASS_THRESHOLD else "FAIL"
        natural = " (natural)" if result.conversation.natural_end else ""
        llm_score_str = ""
        if result.llm_evaluation:
            llm_score_str = f" [LLM: {result.llm_evaluation.score}/5]"
        print(
            f"  [{status}] {result.scenario.name}: {result.score:.2%} "
            f"({result.turn_count} turns{natural}){llm_score_str}"
        )
        if result.topics_missing:
            print(f"       Missing: {', '.join(result.topics_missing)}")

    print("=" * 60)


def print_conversation_detail(result: EvaluationResult) -> None:
    """Print detailed conversation for a single result.

    Args:
        result: The evaluation result to print.
    """
    print(f"\n{'=' * 60}")
    print(f"Scenario: {result.scenario.name}")
    print(f"Description: {result.scenario.description}")
    print(f"Persona: {result.scenario.persona}")
    print(f"{'=' * 60}")

    for turn in result.conversation.turns:
        role_label = "User" if turn.role == "user" else "Support"
        print(f"\n[{role_label}] (Turn {turn.turn_number})")
        print("-" * 40)
        print(turn.message)

    print(f"\n{'=' * 60}")
    print(f"Score: {result.score:.2%}")
    print(f"Topics Covered: {', '.join(result.topics_covered) or 'None'}")
    print(f"Topics Missing: {', '.join(result.topics_missing) or 'None'}")

    # Print LLM evaluation
    if result.llm_evaluation:
        print(f"\nLLM Evaluation Score: {result.llm_evaluation.score}/5")
        print(f"LLM Comment:\n{result.llm_evaluation.comment}")

    print("=" * 60)
