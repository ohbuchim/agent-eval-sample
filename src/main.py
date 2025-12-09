"""Main entry point for agent evaluation."""

import argparse
from datetime import datetime
from pathlib import Path

from src.evaluation.dashboard import save_dashboard, save_results_json
from src.evaluation.evaluator import (
    print_conversation_detail,
    print_evaluation_summary,
    run_evaluation,
)
from src.evaluation.scenarios import (
    EVALUATION_SCENARIOS,
    get_default_scenarios_path,
    load_scenarios_from_json,
)


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
        "--scenarios-json",
        type=str,
        default=None,
        help="Path to JSON file containing evaluation scenarios",
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
    parser.add_argument(
        "--show-conversations",
        action="store_true",
        help="Show detailed conversation logs for each scenario",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save output files (dashboard HTML and results JSON)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Generate HTML dashboard report",
    )
    parser.add_argument(
        "--open-dashboard",
        action="store_true",
        help="Generate and open HTML dashboard in browser",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="シナリオを逐次実行（デフォルトは並列実行）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="並列ワーカー数 (デフォルト: 3)",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=1.0,
        help="ワーカー開始間隔（秒） (デフォルト: 1.0)",
    )

    args = parser.parse_args()

    # Determine scenarios source
    scenarios_json: Path | None = None
    if args.scenarios_json:
        scenarios_json = Path(args.scenarios_json)
        if not scenarios_json.exists():
            print(f"Error: Scenarios file not found: {scenarios_json}")
            return
    else:
        # Use default scenarios JSON
        scenarios_json = get_default_scenarios_path()

    # List scenarios if requested
    if args.list_scenarios:
        print("Available Scenarios:")
        print("-" * 60)

        if scenarios_json and scenarios_json.exists():
            scenario_set = load_scenarios_from_json(scenarios_json)
            scenarios = scenario_set.scenarios
            print(f"Source: {scenarios_json}")
            print(f"Version: {scenario_set.version}")
            print()
        else:
            scenarios = EVALUATION_SCENARIOS

        for scenario in scenarios:
            multi_turn = ""
            if scenario.conversation_flow:
                steps = len(scenario.conversation_flow)
                multi_turn = f" [Multi-turn: {steps} steps]"
            print(f"  {scenario.name}: {scenario.description}{multi_turn}")
            if scenario.persona != "polite":
                print(f"    Persona: {scenario.persona}")
            if scenario.user_context:
                print(f"    Context: {scenario.user_context}")
        return

    # Determine knowledge directory
    knowledge_dir: Path | None = None
    if args.knowledge_dir:
        knowledge_dir = Path(args.knowledge_dir)

    # Determine output directory
    output_dir: Path
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default to project root / output
        output_dir = Path(__file__).parent.parent / "output"

    # Filter scenarios if specific one requested
    filter_scenario = args.scenario

    # Run evaluation
    print("Starting Agent Evaluation")
    print("=" * 60)

    if args.sequential:
        print("実行モード: 逐次")
    else:
        print(f"実行モード: 並列 ({args.workers} ワーカー)")

    if scenarios_json and scenarios_json.exists():
        print(f"Scenarios: {scenarios_json}")

    # Load all scenarios first to filter
    if filter_scenario:
        if scenarios_json and scenarios_json.exists():
            scenario_set = load_scenarios_from_json(scenarios_json)
            all_scenarios = scenario_set.scenarios
        else:
            all_scenarios = EVALUATION_SCENARIOS

        filtered = [s for s in all_scenarios if s.name == filter_scenario]
        if not filtered:
            print(f"Error: Scenario '{filter_scenario}' not found")
            print("Use --list-scenarios to see available scenarios")
            return

        results = run_evaluation(
            knowledge_dir=knowledge_dir,
            scenarios=filtered,
            verbose=not args.quiet,
            parallel=not args.sequential,
            max_workers=args.workers,
            rate_limit_delay=args.rate_limit_delay,
        )
    else:
        results = run_evaluation(
            knowledge_dir=knowledge_dir,
            scenarios_json=scenarios_json if scenarios_json.exists() else None,
            verbose=not args.quiet,
            parallel=not args.sequential,
            max_workers=args.workers,
            rate_limit_delay=args.rate_limit_delay,
        )

    # Show detailed conversations if requested
    if args.show_conversations:
        print("\n" + "=" * 60)
        print("DETAILED CONVERSATIONS")
        print("=" * 60)
        for result in results:
            print_conversation_detail(result)

    # Print summary
    print_evaluation_summary(results)

    # Generate dashboard if requested
    if args.dashboard or args.open_dashboard:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save HTML dashboard
        dashboard_path = output_dir / f"dashboard_{timestamp}.html"
        save_dashboard(results, dashboard_path)
        print(f"\nDashboard saved: {dashboard_path}")

        # Save JSON results
        json_path = output_dir / f"results_{timestamp}.json"
        save_results_json(results, json_path)
        print(f"Results JSON saved: {json_path}")

        # Open dashboard in browser if requested
        if args.open_dashboard:
            import webbrowser

            webbrowser.open(f"file://{dashboard_path.absolute()}")
            print("Dashboard opened in browser")


if __name__ == "__main__":
    main()
