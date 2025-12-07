"""Knowledge base search tool for customer support agent."""

import re
from pathlib import Path

from strands import tool


def _load_knowledge_base(knowledge_dir: Path) -> dict[str, str]:
    """Load all markdown files from the knowledge directory.

    Args:
        knowledge_dir: Path to the knowledge directory.

    Returns:
        Dictionary mapping section titles to their content.
    """
    sections: dict[str, str] = {}

    for md_file in knowledge_dir.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        # Parse markdown sections (## or ### headers)
        current_section = ""
        current_content: list[str] = []

        for line in content.split("\n"):
            if line.startswith("## ") or line.startswith("### "):
                # Save previous section if exists
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

    return sections


def _search_sections(
    sections: dict[str, str], query: str, max_results: int = 3
) -> list[dict[str, str]]:
    """Search sections by keyword matching.

    Args:
        sections: Dictionary of section titles to content.
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        List of matching sections with title and content.
    """
    query_terms = query.lower().split()
    results: list[tuple[int, str, str]] = []

    for title, content in sections.items():
        text = f"{title} {content}".lower()
        # Count matching terms
        score = sum(1 for term in query_terms if term in text)
        if score > 0:
            results.append((score, title, content))

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)

    return [
        {"title": title, "content": content}
        for _, title, content in results[:max_results]
    ]


# Default knowledge directory path (relative to project root)
_KNOWLEDGE_DIR: Path | None = None


def set_knowledge_directory(path: Path | str) -> None:
    """Set the knowledge directory path.

    Args:
        path: Path to the knowledge directory.
    """
    global _KNOWLEDGE_DIR
    _KNOWLEDGE_DIR = Path(path)


def get_knowledge_directory() -> Path:
    """Get the knowledge directory path.

    Returns:
        Path to the knowledge directory.

    Raises:
        ValueError: If knowledge directory is not set.
    """
    if _KNOWLEDGE_DIR is None:
        raise ValueError(
            "Knowledge directory not set. Call set_knowledge_directory() first."
        )
    return _KNOWLEDGE_DIR


@tool
def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for information related to the query.

    Use this tool to find relevant information from the FAQ and documentation
    to answer customer questions accurately.

    Args:
        query: The search query describing what information to find.
            Examples: "返品ポリシー", "配送時間", "パスワード リセット"

    Returns:
        Relevant information from the knowledge base, or a message if no
        results are found.
    """
    try:
        knowledge_dir = get_knowledge_directory()
    except ValueError:
        return "Error: Knowledge directory not configured."

    if not knowledge_dir.exists():
        return f"Error: Knowledge directory not found at {knowledge_dir}"

    sections = _load_knowledge_base(knowledge_dir)

    if not sections:
        return "No knowledge base content found."

    results = _search_sections(sections, query)

    if not results:
        return f"No relevant information found for query: {query}"

    # Format results
    output_parts = ["## 検索結果\n"]
    for i, result in enumerate(results, 1):
        output_parts.append(f"### {i}. {result['title']}\n")
        output_parts.append(result["content"])
        output_parts.append("\n")

    return "\n".join(output_parts)
