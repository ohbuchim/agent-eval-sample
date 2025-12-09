# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install dependencies
uv sync

# Run evaluation (all scenarios)
uv run python -m src.main

# Run specific scenario
uv run python -m src.main --scenario return_policy

# Run with custom scenarios JSON
uv run python -m src.main --scenarios-json path/to/scenarios.json

# List available scenarios
uv run python -m src.main --list-scenarios

# Show detailed conversation logs
uv run python -m src.main --show-conversations

# Generate HTML dashboard
uv run python -m src.main --dashboard

# Generate and open dashboard in browser
uv run python -m src.main --open-dashboard

# Specify output directory for dashboard
uv run python -m src.main --dashboard --output-dir ./reports

# Format and lint
uv run ruff format .
uv run ruff check . --fix

# Type check
uv run pyright

# Run tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD="" uv run pytest
```

## Architecture

This project evaluates AI agents using simulated user agents with Strands Agents SDK.

### Evaluation Flow

1. `evaluator.py` creates a **Customer Support Agent** (target) and a **Simulated User Agent** (tester)
2. The simulated user sends an initial query based on the scenario
3. Agents exchange messages in a multi-turn conversation (configurable max turns)
4. For multi-turn scenarios with `conversation_flow`, the simulated user follows hints to guide the conversation
5. After conversation ends, responses are scored against `expected_topics` defined in each scenario
6. Topic coverage determines the pass/fail score (>= 70% = pass)

### Key Components

- **Customer Support Agent** (`src/agents/customer_support_agent.py`): Target agent that uses `@tool`-decorated `search_knowledge_base` function to answer queries
- **Simulated User Agent** (`src/agents/simulated_user_agent.py`): Plays user personas (POLITE, FRUSTRATED, CONFUSED, DETAILED) defined in `UserPersona` enum
- **Knowledge Search** (`src/tools/knowledge_search.py`): Parses `## ` and `### ` headers from markdown files in `knowledge/` directory
- **Scenarios** (`src/evaluation/scenarios.py`): Loads scenarios from JSON files with support for multi-turn conversation flows
- **Dashboard** (`src/evaluation/dashboard.py`): Generates HTML dashboard reports with conversation logs and scoring details

### Adding New Scenarios

Scenarios are now defined in JSON format. Edit `scenarios/default_scenarios.json` or create a new JSON file:

```json
{
  "version": "1.0",
  "description": "Custom evaluation scenarios",
  "scenarios": [
    {
      "name": "unique_name",
      "description": "Description",
      "initial_query": "User's question",
      "expected_topics": ["keyword1", "keyword2"],
      "expected_tool_use": true,
      "persona": "polite",
      "max_turns": 3,
      "user_context": "Optional context about user situation",
      "user_goal": "What the user wants to achieve",
      "conversation_flow": null
    }
  ]
}
```

### Multi-turn Scenarios

For complex scenarios with predefined conversation flows:

```json
{
  "name": "multi_turn_example",
  "description": "Multi-turn conversation example",
  "initial_query": "Initial question",
  "expected_topics": ["topic1", "topic2"],
  "persona": "polite",
  "max_turns": 6,
  "user_context": "User's situation",
  "user_goal": "User's goal",
  "conversation_flow": [
    {
      "turn": 1,
      "expected_agent_action": "What agent should do",
      "user_response_hint": "How user should respond"
    },
    {
      "turn": 2,
      "expected_agent_action": "Next expected action",
      "user_response_hint": null
    }
  ]
}
```

## AWS Configuration

Uses Amazon Bedrock with Claude models. Required permission: `bedrock:InvokeModel`

```bash
aws configure  # or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
```

Default region: us-west-2
