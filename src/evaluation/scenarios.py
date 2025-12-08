"""Test scenarios for agent evaluation with JSON loading support."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Valid persona values
VALID_PERSONAS = {"polite", "frustrated", "confused", "detailed", "curt"}

# Validation constants
MIN_MAX_TURNS = 1
MAX_MAX_TURNS = 20


@dataclass
class ConversationFlowStep:
    """A single step in a predefined conversation flow.

    Attributes:
        turn: The turn number (1-indexed).
        expected_agent_action: Description of expected agent behavior.
        user_response_hint: Hint for simulated user response, or None if
            conversation ends.
    """

    turn: int
    expected_agent_action: str
    user_response_hint: str | None = None


@dataclass
class EvaluationScenario:
    """A scenario for evaluating the customer support agent.

    Attributes:
        name: Unique identifier for the scenario.
        description: Human-readable description.
        initial_query: The user's initial question.
        expected_topics: Topics that should be covered in the response.
        expected_tool_use: Whether the agent should use the knowledge search tool.
        persona: User persona type (polite, frustrated, confused, detailed).
        max_turns: Maximum number of conversation turns.
        user_context: Additional context about the user's situation.
        user_goal: What the user wants to achieve.
        conversation_flow: Optional predefined conversation flow for
            multi-turn scenarios.
    """

    name: str
    description: str
    initial_query: str
    expected_topics: list[str]
    expected_tool_use: bool = True
    persona: str = "polite"
    max_turns: int = 3
    user_context: str = ""
    user_goal: str = ""
    conversation_flow: list[ConversationFlowStep] | None = None
    scenario_number: int | None = None


@dataclass
class ScenarioSet:
    """A set of evaluation scenarios loaded from a JSON file.

    Attributes:
        version: Schema version.
        description: Description of this scenario set.
        scenarios: List of evaluation scenarios.
        source_file: Path to the source JSON file, if loaded from file.
    """

    version: str
    description: str
    scenarios: list[EvaluationScenario]
    source_file: Path | None = None


def load_scenarios_from_json(json_path: Path | str) -> ScenarioSet:
    """Load evaluation scenarios from a JSON file.

    Args:
        json_path: Path to the JSON file containing scenarios.

    Returns:
        ScenarioSet containing all loaded scenarios.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        json.JSONDecodeError: If the JSON is invalid.
        ValueError: If the JSON structure is invalid.
    """
    json_path = Path(json_path)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Validate required fields
    if "version" not in data:
        raise ValueError("JSON must contain 'version' field")
    if "scenarios" not in data:
        raise ValueError("JSON must contain 'scenarios' array")

    scenarios: list[EvaluationScenario] = []

    for i, scenario_data in enumerate(data["scenarios"]):
        # Validate required fields for each scenario
        required_fields = ["name", "description", "initial_query", "expected_topics"]
        for field_name in required_fields:
            if field_name not in scenario_data:
                raise ValueError(f"Scenario {i} missing required field '{field_name}'")

        # Validate max_turns
        max_turns = scenario_data.get("max_turns", 3)
        if not isinstance(max_turns, int) or max_turns < MIN_MAX_TURNS:
            raise ValueError(
                f"Scenario {i} ({scenario_data['name']}): "
                f"max_turns must be a positive integer, got {max_turns}"
            )
        if max_turns > MAX_MAX_TURNS:
            logger.warning(
                f"Scenario {i} ({scenario_data['name']}): "
                f"max_turns={max_turns} is unusually high "
                f"(max recommended: {MAX_MAX_TURNS})"
            )

        # Validate persona
        persona = scenario_data.get("persona", "polite")
        if persona not in VALID_PERSONAS:
            raise ValueError(
                f"Scenario {i} ({scenario_data['name']}): "
                f"invalid persona '{persona}'. Must be one of: {sorted(VALID_PERSONAS)}"
            )

        # Validate expected_topics is non-empty
        expected_topics = scenario_data["expected_topics"]
        if not isinstance(expected_topics, list) or len(expected_topics) == 0:
            raise ValueError(
                f"Scenario {i} ({scenario_data['name']}): "
                "expected_topics must be a non-empty list"
            )

        # Parse conversation flow if present
        conversation_flow = None
        if scenario_data.get("conversation_flow"):
            conversation_flow = [
                ConversationFlowStep(
                    turn=step["turn"],
                    expected_agent_action=step["expected_agent_action"],
                    user_response_hint=step.get("user_response_hint"),
                )
                for step in scenario_data["conversation_flow"]
            ]

        scenario = EvaluationScenario(
            name=scenario_data["name"],
            description=scenario_data["description"],
            initial_query=scenario_data["initial_query"],
            expected_topics=scenario_data["expected_topics"],
            expected_tool_use=scenario_data.get("expected_tool_use", True),
            persona=scenario_data.get("persona", "polite"),
            max_turns=scenario_data.get("max_turns", 3),
            user_context=scenario_data.get("user_context", ""),
            user_goal=scenario_data.get("user_goal", ""),
            conversation_flow=conversation_flow,
            scenario_number=scenario_data.get("scenario_number"),
        )
        scenarios.append(scenario)

    return ScenarioSet(
        version=data["version"],
        description=data.get("description", ""),
        scenarios=scenarios,
        source_file=json_path,
    )


def get_default_scenarios_path() -> Path:
    """Get the path to the default scenarios JSON file.

    Returns:
        Path to default_scenarios.json in the scenarios directory.
    """
    project_root = Path(__file__).parent.parent.parent
    return project_root / "scenarios" / "default_scenarios.json"


def load_default_scenarios() -> list[EvaluationScenario]:
    """Load the default evaluation scenarios.

    Returns:
        List of default evaluation scenarios.
    """
    default_path = get_default_scenarios_path()
    if default_path.exists():
        scenario_set = load_scenarios_from_json(default_path)
        return scenario_set.scenarios
    else:
        # Fallback to hardcoded scenarios if JSON doesn't exist
        return _get_fallback_scenarios()


def _get_fallback_scenarios() -> list[EvaluationScenario]:
    """Get fallback hardcoded scenarios.

    Returns:
        List of basic evaluation scenarios.
    """
    return [
        EvaluationScenario(
            name="return_policy",
            description="返品ポリシーに関する質問",
            initial_query="商品を返品したいのですが、どうすればいいですか？",
            expected_topics=["30日以内", "未使用・未開封", "返品送料"],
        ),
        EvaluationScenario(
            name="warranty",
            description="保証期間に関する質問",
            initial_query="製品の保証について教えてください",
            expected_topics=["1年間", "メーカー保証", "製造上の欠陥"],
        ),
    ]


# Default scenarios (loaded lazily)
_default_scenarios: list[EvaluationScenario] | None = None


def get_evaluation_scenarios() -> list[EvaluationScenario]:
    """Get the default evaluation scenarios (lazy loading).

    Returns:
        List of default evaluation scenarios.
    """
    global _default_scenarios
    if _default_scenarios is None:
        _default_scenarios = load_default_scenarios()
    return _default_scenarios


# For backward compatibility
EVALUATION_SCENARIOS: list[EvaluationScenario] = []


def _init_default_scenarios() -> None:
    """Initialize EVALUATION_SCENARIOS for backward compatibility."""
    global EVALUATION_SCENARIOS
    EVALUATION_SCENARIOS = load_default_scenarios()


# Initialize on module load
_init_default_scenarios()
