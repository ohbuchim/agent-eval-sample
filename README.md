# Agent Eval Sample

Agent evaluation sample using simulated user agents with Strands Agents SDK.

## Overview

This project demonstrates how to evaluate AI agents using simulated user agents. The target agent is a customer support agent that searches a knowledge base (Markdown files) to provide accurate answers.

## Architecture

```
src/
├── agents/
│   ├── customer_support_agent.py  # Target agent with knowledge search tool
│   └── simulated_user_agent.py    # Agent that simulates user behavior
├── tools/
│   └── knowledge_search.py        # Knowledge base search tool
├── evaluation/
│   ├── evaluator.py               # Evaluation orchestration
│   └── scenarios.py               # Test scenarios/cases
└── main.py                        # Entry point

knowledge/                          # Knowledge base (Markdown files)
└── sample_faq.md
```

## Setup

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras
```

## Usage

```bash
# Run evaluation
uv run python -m src.main
```

## AWS Configuration

This project uses Amazon Bedrock. Configure your AWS credentials:

```bash
aws configure
```

Required permissions:
- `bedrock:InvokeModel` for Claude models

## Development

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run pyright

# Run tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD="" uv run pytest
```
