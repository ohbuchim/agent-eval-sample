"""Main entry point for agent evaluation."""

import argparse
from pathlib import Path

from src.evaluation.evaluator import (
    print_evaluation_summary,
    run_evaluation,
)
from src.evaluation.scenarios import EVALUATION_SCENARIOS


def main() -> None:
    """Run the agent evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate customer support agent using simulated users"
    )
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=None,
        help="Path to knowledge directory (default: ./knowledge)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run a specific scenario by name",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List all available scenarios",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    # List scenarios if requested
    if args.list_scenarios:
        print("Available Scenarios:")
        print("-" * 40)
        for scenario in EVALUATION_SCENARIOS:
            print(f"  {scenario.name}: {scenario.description}")
        return

    # Determine knowledge directory
    knowledge_dir: Path | None = None
    if args.knowledge_dir:
        knowledge_dir = Path(args.knowledge_dir)

    # Filter scenarios if specific one requested
    scenarios = EVALUATION_SCENARIOS
    if args.scenario:
        scenarios = [s for s in EVALUATION_SCENARIOS if s.name == args.scenario]
        if not scenarios:
            print(f"Error: Scenario '{args.scenario}' not found")
            print("Use --list-scenarios to see available scenarios")
            return

    # Run evaluation
    print("Starting Agent Evaluation")
    print("=" * 60)

    results = run_evaluation(
        knowledge_dir=knowledge_dir,
        scenarios=scenarios,
        verbose=not args.quiet,
    )

    # Print summary
    print_evaluation_summary(results)


if __name__ == "__main__":
    main()
