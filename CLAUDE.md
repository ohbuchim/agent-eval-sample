# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Agent Eval Sample is a demonstration project that shows how to evaluate AI agents using simulated user agents. The project uses Strands Agents SDK and targets a customer support agent with knowledge base search capability.

## Development Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run evaluation
uv run python -m src.main

# Run specific scenario
uv run python -m src.main --scenario return_policy

# List available scenarios
uv run python -m src.main --list-scenarios

# Format code
uv run ruff format .

# Lint
uv run ruff check .
uv run ruff check . --fix

# Type check
uv run pyright

# Run tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD="" uv run pytest
```

## Architecture

```
agent-eval-sample/
├── src/
│   ├── agents/
│   │   ├── customer_support_agent.py  # Target agent (knowledge search tool)
│   │   └── simulated_user_agent.py    # Simulated user agent
│   ├── tools/
│   │   └── knowledge_search.py        # Knowledge base search tool
│   ├── evaluation/
│   │   ├── evaluator.py               # Evaluation orchestration
│   │   └── scenarios.py               # Test scenarios
│   └── main.py                        # Entry point
├── knowledge/                          # Knowledge base (Markdown files)
│   └── sample_faq.md
└── tests/
```

### Key Components

1. **Customer Support Agent** (`src/agents/customer_support_agent.py`)
   - Uses Strands Agents SDK
   - Has access to `search_knowledge_base` tool
   - Searches markdown files for relevant information

2. **Simulated User Agent** (`src/agents/simulated_user_agent.py`)
   - Simulates different user personas (polite, frustrated, confused, detailed)
   - Used to test the customer support agent

3. **Knowledge Search Tool** (`src/tools/knowledge_search.py`)
   - Parses markdown files in `knowledge/` directory
   - Simple keyword-based search

4. **Evaluation Logic** (`src/evaluation/`)
   - `scenarios.py`: Defines test scenarios with expected topics
   - `evaluator.py`: Runs conversations and scores results

## Code Standards

### Python
- Use **uv** for package management (pip is prohibited)
- Type hints required on all functions
- Use `| None` instead of `Optional`
- Google-style docstrings for public APIs
- Ruff for formatting (88 char line length)
- Pyright for type checking

### Testing
- Framework: pytest with anyio for async tests
- Test files: `test_*.py`

## AWS Configuration

This project uses Amazon Bedrock with Claude models.

Required AWS permissions:
- `bedrock:InvokeModel`

Configure credentials:
```bash
aws configure
# Or set environment variables:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
```

Default region: us-west-2
