"""Evaluation logic for customer support agent using simulated users."""

from dataclasses import dataclass, field
from pathlib import Path

from strands import Agent

from src.agents.customer_support_agent import (
    create_customer_support_agent,
    get_customer_support_response,
)
from src.agents.simulated_user_agent import (
    UserScenario,
    create_simulated_user_agent,
    get_simulated_user_response,
)
from src.evaluation.scenarios import EVALUATION_SCENARIOS, EvaluationScenario


@dataclass
class ConversationTurn:
    """A single turn in the conversation.

    Attributes:
        role: Either "user" or "support".
        message: The message content.
    """

    role: str
    message: str


@dataclass
class ConversationResult:
    """Result of a simulated conversation.

    Attributes:
        scenario_name: Name of the evaluation scenario.
        turns: List of conversation turns.
        completed: Whether the conversation completed successfully.
        error: Error message if any.
    """

    scenario_name: str
    turns: list[ConversationTurn] = field(default_factory=list)
    completed: bool = False
    error: str | None = None


@dataclass
class EvaluationResult:
    """Result of evaluating a single scenario.

    Attributes:
        scenario: The evaluation scenario.
        conversation: The conversation result.
        topics_covered: List of expected topics that were covered.
        topics_missing: List of expected topics that were not covered.
        score: Overall score (0.0 to 1.0).
    """

    scenario: EvaluationScenario
    conversation: ConversationResult
    topics_covered: list[str] = field(default_factory=list)
    topics_missing: list[str] = field(default_factory=list)
    score: float = 0.0


def run_conversation(
    support_agent: Agent,
    user_scenario: UserScenario,
    max_turns: int = 6,
) -> ConversationResult:
    """Run a simulated conversation between user and support agent.

    Args:
        support_agent: The customer support agent.
        user_scenario: The user scenario to simulate.
        max_turns: Maximum number of total turns (user + support).

    Returns:
        The conversation result.
    """
    result = ConversationResult(scenario_name=user_scenario.goal)

    try:
        # Create simulated user agent (disable console output)
        user_agent = create_simulated_user_agent(
            scenario=user_scenario,
            callback_handler=None,
        )

        # Start with the initial query
        user_message = user_scenario.initial_query
        result.turns.append(ConversationTurn(role="user", message=user_message))

        for turn in range(max_turns):
            # Get support agent response
            support_response = get_customer_support_response(
                support_agent, user_message
            )
            result.turns.append(
                ConversationTurn(role="support", message=support_response)
            )

            # Check if this is the last allowed turn
            if turn >= max_turns - 1:
                break

            # Get simulated user response
            user_message = get_simulated_user_response(user_agent, support_response)
            result.turns.append(ConversationTurn(role="user", message=user_message))

            # Check if conversation ended (user said thanks)
            if any(
                phrase in user_message
                for phrase in ["ありがとうございました", "ありがとうございます", "助かりました"]
            ):
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
) -> EvaluationResult:
    """Evaluate a conversation against expected criteria.

    Args:
        scenario: The evaluation scenario.
        conversation: The conversation result.

    Returns:
        The evaluation result with scores.
    """
    result = EvaluationResult(
        scenario=scenario,
        conversation=conversation,
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

    return result


def run_evaluation(
    knowledge_dir: Path | str | None = None,
    scenarios: list[EvaluationScenario] | None = None,
    verbose: bool = True,
) -> list[EvaluationResult]:
    """Run evaluation for multiple scenarios.

    Args:
        knowledge_dir: Path to the knowledge directory.
        scenarios: List of scenarios to evaluate. If None, uses all default scenarios.
        verbose: Whether to print progress.

    Returns:
        List of evaluation results.
    """
    if scenarios is None:
        scenarios = EVALUATION_SCENARIOS

    # Create support agent (disable console output for evaluation)
    support_agent = create_customer_support_agent(
        knowledge_dir=knowledge_dir,
        callback_handler=None,
    )

    results: list[EvaluationResult] = []

    for i, scenario in enumerate(scenarios, 1):
        if verbose:
            print(f"\n[{i}/{len(scenarios)}] Evaluating: {scenario.description}")

        # Create a user scenario from evaluation scenario
        from src.agents.simulated_user_agent import UserPersona

        user_scenario = UserScenario(
            persona=UserPersona.POLITE,
            initial_query=scenario.initial_query,
            goal=scenario.description,
            max_turns=3,
        )

        # Run conversation
        conversation = run_conversation(
            support_agent=support_agent,
            user_scenario=user_scenario,
        )

        # Evaluate
        eval_result = evaluate_conversation(scenario, conversation)
        results.append(eval_result)

        if verbose:
            print(f"  Score: {eval_result.score:.2%}")
            if eval_result.topics_missing:
                print(f"  Missing topics: {', '.join(eval_result.topics_missing)}")

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

    passed = sum(1 for r in results if r.score >= 0.7)
    print(f"Passed (>= 70%): {passed}/{len(results)}")

    print("\nDetailed Results:")
    print("-" * 60)

    for result in results:
        status = "PASS" if result.score >= 0.7 else "FAIL"
        print(f"  [{status}] {result.scenario.name}: {result.score:.2%}")
        if result.topics_missing:
            print(f"       Missing: {', '.join(result.topics_missing)}")

    print("=" * 60)
