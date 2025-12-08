"""HTML dashboard generator for evaluation results."""

import html
import json
from datetime import datetime
from pathlib import Path

from src.evaluation.evaluator import (
    PARTIAL_THRESHOLD,
    PASS_THRESHOLD,
    EvaluationResult,
)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(text)


def _format_message_html(message: str) -> str:
    """Format a message for HTML display with proper line breaks."""
    escaped = _escape_html(message)
    # Convert newlines to <br> tags
    return escaped.replace("\n", "<br>")


def _get_status_class(score: float) -> str:
    """Get CSS class based on score."""
    if score >= PASS_THRESHOLD:
        return "pass"
    elif score >= PARTIAL_THRESHOLD:
        return "partial"
    else:
        return "fail"


def _get_status_label(score: float) -> str:
    """Get status label based on score."""
    if score >= PASS_THRESHOLD:
        return "PASS"
    elif score >= PARTIAL_THRESHOLD:
        return "PARTIAL"
    else:
        return "FAIL"


def _render_context_html(context: str) -> str:
    """Render context HTML if context exists."""
    if not context:
        return ""
    escaped = _escape_html(context)
    return f'<div class="meta-item"><strong>Context:</strong> {escaped}</div>'


def _render_goal_html(goal: str) -> str:
    """Render goal HTML if goal exists."""
    if not goal:
        return ""
    escaped = _escape_html(goal)
    return f'<div class="meta-item"><strong>Goal:</strong> {escaped}</div>'


def generate_dashboard_html(
    results: list[EvaluationResult],
    title: str = "Agent Evaluation Dashboard",
) -> str:
    """Generate HTML dashboard for evaluation results.

    Args:
        results: List of evaluation results.
        title: Dashboard title.

    Returns:
        HTML string for the dashboard.
    """
    # Sort results by scenario_number (ascending), placing None values at the end
    sorted_results = sorted(
        results,
        key=lambda r: (
            r.scenario.scenario_number is None,
            r.scenario.scenario_number if r.scenario.scenario_number is not None else 0,
        ),
    )

    # Calculate summary statistics
    total = len(results)
    passed = sum(1 for r in results if r.score >= PASS_THRESHOLD)
    failed = total - passed
    avg_score = sum(r.score for r in results) / total if total > 0 else 0
    avg_turns = sum(r.turn_count for r in results) / total if total > 0 else 0
    natural_ends = sum(1 for r in results if r.conversation.natural_end)

    # Generate scenario cards
    scenario_cards = []
    for i, result in enumerate(sorted_results):
        status_class = _get_status_class(result.score)
        status_label = _get_status_label(result.score)

        # Generate conversation HTML
        conversation_html = []
        tool_use_counter = 0
        for turn in result.conversation.turns:
            role_class = "user" if turn.role == "user" else "agent"
            role_label = "User" if turn.role == "user" else "Agent"
            message_html = _format_message_html(turn.message)

            # Generate tool usage HTML for this turn
            tool_uses_html = ""
            tool_count_badge = ""
            if turn.tool_uses:
                tool_count = len(turn.tool_uses)
                tool_count_badge = (
                    f'<span class="tool-count" '
                    f"onclick=\"toggleTools(event, 'tools-{i}-{tool_use_counter}')\">"
                    f"🔧 {tool_count} tool{'s' if tool_count > 1 else ''}</span>"
                )

                tool_items = []
                for tu in turn.tool_uses:
                    escaped_input = _escape_html(
                        json.dumps(tu.tool_input, ensure_ascii=False, indent=2)
                    )
                    escaped_output = _escape_html(tu.tool_output)
                    tool_name_escaped = _escape_html(tu.tool_name)
                    tool_items.append(f"""
                        <div class="tool-use">
                            <div class="tool-header">
                                <span class="tool-name">{tool_name_escaped}</span>
                            </div>
                            <div class="tool-detail">
                                <div class="tool-input">
                                    <strong>Input:</strong>
                                    <pre>{escaped_input}</pre>
                                </div>
                                <div class="tool-output">
                                    <strong>Output:</strong>
                                    <pre>{escaped_output}</pre>
                                </div>
                            </div>
                        </div>
                    """)

                tool_uses_html = f"""
                    <div class="tool-uses" id="tools-{i}-{tool_use_counter}">
                        {"".join(tool_items)}
                    </div>
                """
                tool_use_counter += 1

            conversation_html.append(f"""
                <div class="message {role_class}">
                    <div class="message-header">
                        <span class="role">{role_label}</span>
                        <span class="turn">Turn {turn.turn_number}</span>
                        {tool_count_badge}
                    </div>
                    {tool_uses_html}
                    <div class="message-content">{message_html}</div>
                </div>
            """)

        # Topics HTML
        covered_html = "".join(
            f'<span class="topic covered">{_escape_html(t)}</span>'
            for t in result.topics_covered
        )
        missing_html = "".join(
            f'<span class="topic missing">{_escape_html(t)}</span>'
            for t in result.topics_missing
        )

        # Natural end indicator
        natural_indicator = (
            '<span class="natural-end">Natural End</span>'
            if result.conversation.natural_end
            else ""
        )

        # Error message if any
        error_html = ""
        if result.conversation.error:
            error_html = f"""
                <div class="error-message">
                    <strong>Error:</strong> {_escape_html(result.conversation.error)}
                </div>
            """

        # LLM evaluation section
        llm_eval_html = ""
        llm_score_badge = ""
        if result.llm_evaluation:
            llm_score = result.llm_evaluation.score
            llm_score_class = (
                "high" if llm_score >= 4 else "medium" if llm_score >= 3 else "low"
            )
            llm_score_badge = (
                f'<span class="llm-score {llm_score_class}">{llm_score}/5</span>'
            )
            llm_eval_html = f"""
                <div class="llm-evaluation-section">
                    <h4>LLM Evaluation</h4>
                    <div class="llm-score-display {llm_score_class}">
                        <span class="llm-score-value">{llm_score}</span>
                        <span class="llm-score-max">/5</span>
                    </div>
                    <div class="llm-comment">
                        {_format_message_html(result.llm_evaluation.comment)}
                    </div>
                </div>
            """

        # Format scenario title with number
        scenario_title = (
            f"#{result.scenario.scenario_number} {result.scenario.name}"
            if result.scenario.scenario_number is not None
            else result.scenario.name
        )

        scenario_cards.append(f"""
            <div class="scenario-card {status_class}" id="scenario-{i}">
                <div class="scenario-header" onclick="toggleScenario({i})">
                    <div class="scenario-title">
                        <span class="status-badge {status_class}">{status_label}</span>
                        <h3>{_escape_html(scenario_title)}</h3>
                        <span class="scenario-desc">
                            {_escape_html(result.scenario.description)}
                        </span>
                    </div>
                    <div class="scenario-stats">
                        <span class="score">{result.score:.0%}</span>
                        {llm_score_badge}
                        <span class="turns">{result.turn_count} turns</span>
                        {natural_indicator}
                        <span class="toggle-icon">▼</span>
                    </div>
                </div>
                <div class="scenario-details" id="details-{i}">
                    {llm_eval_html}
                    <div class="scenario-meta">
                        <div class="meta-item">
                            <strong>Persona:</strong> {result.scenario.persona}
                        </div>
                        <div class="meta-item">
                            <strong>Initial Query:</strong>
                            {_escape_html(result.scenario.initial_query)}
                        </div>
                        {_render_context_html(result.scenario.user_context)}
                        {_render_goal_html(result.scenario.user_goal)}
                    </div>
                    {error_html}
                    <div class="topics-section">
                        <div class="topics-header">
                            <h4>Expected Topics</h4>
                            <div class="topics-legend">
                                <span class="legend-item">
                                    <span class="topic covered">Covered</span>
                                </span>
                                <span class="legend-item">
                                    <span class="topic missing">Missing</span>
                                </span>
                            </div>
                        </div>
                        <div class="topics">
                            {covered_html}
                            {missing_html}
                        </div>
                    </div>
                    <div class="conversation-section">
                        <h4>Conversation Log</h4>
                        <div class="conversation">
                            {"".join(conversation_html)}
                        </div>
                    </div>
                </div>
            </div>
        """)

    # Generate full HTML
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape_html(title)}</title>
    <style>
        :root {{
            --pass-color: #10b981;
            --pass-bg: #d1fae5;
            --fail-color: #ef4444;
            --fail-bg: #fee2e2;
            --partial-color: #f59e0b;
            --partial-bg: #fef3c7;
            --user-color: #3b82f6;
            --user-bg: #dbeafe;
            --agent-color: #8b5cf6;
            --agent-bg: #ede9fe;
            --border-color: #e5e7eb;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --bg-primary: #ffffff;
            --bg-secondary: #f9fafb;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                'Helvetica Neue', Arial, sans-serif;
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            margin-bottom: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}

        header h1 {{
            font-size: 2rem;
            margin-bottom: 10px;
        }}

        .timestamp {{
            opacity: 0.8;
            font-size: 0.9rem;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: var(--bg-primary);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border-color);
        }}

        .summary-card.pass {{
            border-left: 4px solid var(--pass-color);
        }}

        .summary-card.fail {{
            border-left: 4px solid var(--fail-color);
        }}

        .summary-value {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .summary-card.pass .summary-value {{
            color: var(--pass-color);
        }}

        .summary-card.fail .summary-value {{
            color: var(--fail-color);
        }}

        .summary-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .filter-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 8px 16px;
            border: 1px solid var(--border-color);
            background: var(--bg-primary);
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}

        .filter-btn:hover {{
            background: var(--bg-secondary);
        }}

        .filter-btn.active {{
            background: var(--text-primary);
            color: white;
            border-color: var(--text-primary);
        }}

        .scenario-card {{
            background: var(--bg-primary);
            border-radius: 12px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border-color);
            overflow: hidden;
        }}

        .scenario-card.pass {{
            border-left: 4px solid var(--pass-color);
        }}

        .scenario-card.fail {{
            border-left: 4px solid var(--fail-color);
        }}

        .scenario-card.partial {{
            border-left: 4px solid var(--partial-color);
        }}

        .scenario-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}

        .scenario-header:hover {{
            background-color: var(--bg-secondary);
        }}

        .scenario-title {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .scenario-title h3 {{
            font-size: 1.1rem;
            font-weight: 600;
        }}

        .scenario-desc {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .status-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .status-badge.pass {{
            background: var(--pass-bg);
            color: var(--pass-color);
        }}

        .status-badge.fail {{
            background: var(--fail-bg);
            color: var(--fail-color);
        }}

        .status-badge.partial {{
            background: var(--partial-bg);
            color: var(--partial-color);
        }}

        .scenario-stats {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .score {{
            font-size: 1.5rem;
            font-weight: bold;
        }}

        .scenario-card.pass .score {{
            color: var(--pass-color);
        }}

        .scenario-card.fail .score {{
            color: var(--fail-color);
        }}

        .scenario-card.partial .score {{
            color: var(--partial-color);
        }}

        .turns {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .natural-end {{
            background: #dbeafe;
            color: #3b82f6;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }}

        .llm-score {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: bold;
        }}

        .llm-score.high {{
            background: var(--pass-bg);
            color: var(--pass-color);
        }}

        .llm-score.medium {{
            background: var(--partial-bg);
            color: var(--partial-color);
        }}

        .llm-score.low {{
            background: var(--fail-bg);
            color: var(--fail-color);
        }}

        .llm-evaluation-section {{
            margin-top: 20px;
            padding: 20px;
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }}

        .llm-evaluation-section h4 {{
            margin-bottom: 15px;
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .llm-score-display {{
            display: inline-flex;
            align-items: baseline;
            padding: 10px 20px;
            border-radius: 12px;
            margin-bottom: 15px;
        }}

        .llm-score-display.high {{
            background: var(--pass-bg);
        }}

        .llm-score-display.medium {{
            background: var(--partial-bg);
        }}

        .llm-score-display.low {{
            background: var(--fail-bg);
        }}

        .llm-score-value {{
            font-size: 2rem;
            font-weight: bold;
        }}

        .llm-score-display.high .llm-score-value {{
            color: var(--pass-color);
        }}

        .llm-score-display.medium .llm-score-value {{
            color: var(--partial-color);
        }}

        .llm-score-display.low .llm-score-value {{
            color: var(--fail-color);
        }}

        .llm-score-max {{
            font-size: 1rem;
            color: var(--text-secondary);
            margin-left: 2px;
        }}

        .llm-comment {{
            font-size: 0.95rem;
            line-height: 1.7;
            color: var(--text-primary);
            padding: 15px;
            background: var(--bg-primary);
            border-radius: 8px;
            border-left: 3px solid var(--agent-color);
        }}

        .toggle-icon {{
            color: var(--text-secondary);
            transition: transform 0.3s;
        }}

        .scenario-card.expanded .toggle-icon {{
            transform: rotate(180deg);
        }}

        .scenario-details {{
            display: none;
            padding: 0 20px 20px;
            border-top: 1px solid var(--border-color);
        }}

        .scenario-card.expanded .scenario-details {{
            display: block;
        }}

        .scenario-meta {{
            background: var(--bg-secondary);
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }}

        .meta-item {{
            margin-bottom: 8px;
        }}

        .meta-item:last-child {{
            margin-bottom: 0;
        }}

        .meta-item strong {{
            color: var(--text-secondary);
        }}

        .error-message {{
            background: var(--fail-bg);
            color: var(--fail-color);
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }}

        .topics-section {{
            margin: 20px 0;
        }}

        .topics-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}

        .topics-section h4 {{
            margin: 0;
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .topics {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .topic {{
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.85rem;
        }}

        .topic.covered {{
            background: var(--pass-bg);
            color: var(--pass-color);
        }}

        .topic.missing {{
            background: var(--fail-bg);
            color: var(--fail-color);
            text-decoration: line-through;
        }}

        .topics-legend {{
            display: flex;
            gap: 10px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .legend-item {{
            margin-right: 15px;
        }}

        .conversation-section {{
            margin-top: 20px;
        }}

        .conversation-section h4 {{
            margin-bottom: 15px;
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .conversation {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .message {{
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
        }}

        .message.user {{
            background: var(--user-bg);
            border-left: 3px solid var(--user-color);
            align-self: flex-start;
        }}

        .message.agent {{
            background: var(--agent-bg);
            border-left: 3px solid var(--agent-color);
            align-self: flex-end;
        }}

        .message-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.8rem;
        }}

        .message.user .role {{
            color: var(--user-color);
            font-weight: 600;
        }}

        .message.agent .role {{
            color: var(--agent-color);
            font-weight: 600;
        }}

        .turn {{
            color: var(--text-secondary);
        }}

        .message-content {{
            font-size: 0.95rem;
            line-height: 1.6;
        }}

        .tool-count {{
            background: #e0e7ff;
            color: #4f46e5;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            cursor: pointer;
            margin-left: 8px;
        }}

        .tool-count:hover {{
            background: #c7d2fe;
        }}

        .tool-uses {{
            background: #f8fafc;
            border-left: 3px solid #4f46e5;
            margin: 10px 0;
            padding: 12px;
            border-radius: 4px;
            display: none;
        }}

        .tool-uses.expanded {{
            display: block;
        }}

        .tool-use {{
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px dashed #e2e8f0;
        }}

        .tool-use:last-child {{
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }}

        .tool-header {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}

        .tool-name {{
            font-weight: 600;
            color: #4f46e5;
            font-size: 0.9rem;
        }}

        .tool-detail {{
            font-size: 0.85rem;
        }}

        .tool-input, .tool-output {{
            margin: 8px 0;
        }}

        .tool-input strong, .tool-output strong {{
            display: block;
            color: var(--text-secondary);
            font-size: 0.8rem;
            margin-bottom: 4px;
        }}

        .tool-input pre, .tool-output pre {{
            background: #f1f5f9;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.8rem;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 0;
        }}

        .expand-all-bar {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 15px;
        }}

        .expand-all-btn {{
            padding: 8px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}

        .expand-all-btn:hover {{
            background: var(--bg-secondary);
        }}

        footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        @media (max-width: 768px) {{
            .scenario-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }}

            .scenario-stats {{
                width: 100%;
                justify-content: flex-start;
            }}

            .message {{
                max-width: 95%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{_escape_html(title)}</h1>
            <div class="timestamp">Generated: {timestamp}</div>
        </header>

        <div class="summary">
            <div class="summary-card">
                <div class="summary-value">{total}</div>
                <div class="summary-label">Total Scenarios</div>
            </div>
            <div class="summary-card pass">
                <div class="summary-value">{passed}</div>
                <div class="summary-label">Passed</div>
            </div>
            <div class="summary-card fail">
                <div class="summary-value">{failed}</div>
                <div class="summary-label">Failed</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{avg_score:.0%}</div>
                <div class="summary-label">Avg Score</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{avg_turns:.1f}</div>
                <div class="summary-label">Avg Turns</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{natural_ends}</div>
                <div class="summary-label">Natural Ends</div>
            </div>
        </div>

        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterScenarios('all')">
                All ({total})
            </button>
            <button class="filter-btn" onclick="filterScenarios('pass')">
                Passed ({passed})
            </button>
            <button class="filter-btn" onclick="filterScenarios('fail')">
                Failed ({failed})
            </button>
        </div>

        <div class="expand-all-bar">
            <button class="expand-all-btn" onclick="toggleAll()">
                Expand/Collapse All
            </button>
        </div>

        <div class="scenarios" id="scenarios">
            {"".join(scenario_cards)}
        </div>

        <footer>
            Agent Evaluation Dashboard - Powered by Strands Agents SDK
        </footer>
    </div>

    <script>
        function toggleScenario(index) {{
            const card = document.getElementById('scenario-' + index);
            card.classList.toggle('expanded');
        }}

        function filterScenarios(filter) {{
            const cards = document.querySelectorAll('.scenario-card');
            const buttons = document.querySelectorAll('.filter-btn');

            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            cards.forEach(card => {{
                if (filter === 'all') {{
                    card.style.display = 'block';
                }} else if (filter === 'pass') {{
                    card.style.display = card.classList.contains('pass')
                        ? 'block' : 'none';
                }} else if (filter === 'fail') {{
                    card.style.display = (
                        card.classList.contains('fail') ||
                        card.classList.contains('partial')
                    ) ? 'block' : 'none';
                }}
            }});
        }}

        let allExpanded = false;
        function toggleAll() {{
            const cards = document.querySelectorAll('.scenario-card');
            allExpanded = !allExpanded;
            cards.forEach(card => {{
                if (allExpanded) {{
                    card.classList.add('expanded');
                }} else {{
                    card.classList.remove('expanded');
                }}
            }});
        }}

        function toggleTools(event, toolsId) {{
            event.stopPropagation();
            const toolsDiv = document.getElementById(toolsId);
            if (toolsDiv) {{
                toolsDiv.classList.toggle('expanded');
            }}
        }}
    </script>
</body>
</html>
"""

    return html_content


def save_dashboard(
    results: list[EvaluationResult],
    output_path: Path | str,
    title: str = "Agent Evaluation Dashboard",
) -> Path:
    """Generate and save HTML dashboard.

    Args:
        results: List of evaluation results.
        output_path: Path to save the HTML file.
        title: Dashboard title.

    Returns:
        Path to the saved HTML file.
    """
    output_path = Path(output_path)
    html_content = generate_dashboard_html(results, title)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path


def save_results_json(
    results: list[EvaluationResult],
    output_path: Path | str,
) -> Path:
    """Save evaluation results as JSON for later analysis.

    Args:
        results: List of evaluation results.
        output_path: Path to save the JSON file.

    Returns:
        Path to the saved JSON file.
    """
    output_path = Path(output_path)

    # Calculate average LLM score
    llm_scores = [
        r.llm_evaluation.score for r in results if r.llm_evaluation is not None
    ]
    avg_llm_score = sum(llm_scores) / len(llm_scores) if llm_scores else None

    data = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.score >= PASS_THRESHOLD),
            "failed": sum(1 for r in results if r.score < PASS_THRESHOLD),
            "average_score": (
                sum(r.score for r in results) / len(results) if results else 0
            ),
            "average_turns": (
                sum(r.turn_count for r in results) / len(results) if results else 0
            ),
            "average_llm_score": avg_llm_score,
        },
        "results": [
            {
                "scenario": {
                    "name": r.scenario.name,
                    "description": r.scenario.description,
                    "initial_query": r.scenario.initial_query,
                    "expected_topics": r.scenario.expected_topics,
                    "persona": r.scenario.persona,
                    "max_turns": r.scenario.max_turns,
                    "user_context": r.scenario.user_context,
                    "user_goal": r.scenario.user_goal,
                    "scenario_number": r.scenario.scenario_number,
                },
                "score": r.score,
                "turn_count": r.turn_count,
                "topics_covered": r.topics_covered,
                "topics_missing": r.topics_missing,
                "natural_end": r.conversation.natural_end,
                "error": r.conversation.error,
                "llm_evaluation": (
                    {
                        "score": r.llm_evaluation.score,
                        "comment": r.llm_evaluation.comment,
                    }
                    if r.llm_evaluation
                    else None
                ),
                "conversation": [
                    {
                        "role": t.role,
                        "turn_number": t.turn_number,
                        "message": t.message,
                        "tool_uses": [
                            {
                                "tool_name": tu.tool_name,
                                "tool_input": tu.tool_input,
                                "tool_output": tu.tool_output,
                            }
                            for tu in t.tool_uses
                        ],
                    }
                    for t in r.conversation.turns
                ],
            }
            for r in results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path
