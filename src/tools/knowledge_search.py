"""Knowledge base search tool for customer support agent using semantic search."""

import json
import logging
import os
import threading
from pathlib import Path

import boto3
import numpy as np
from botocore.exceptions import ClientError, NoCredentialsError
from numpy.typing import NDArray
from strands import tool

logger = logging.getLogger(__name__)

# Bedrock client for embeddings
_bedrock_client = None

# Embedding model ID
EMBEDDING_MODEL_ID = "cohere.embed-multilingual-v3"

# Search constants
DEFAULT_MAX_RESULTS = 3
DEFAULT_MIN_SIMILARITY_SCORE = 0.3

# Cache for knowledge base embeddings
_kb_cache: dict[str, tuple[list[dict[str, str]], NDArray[np.float32]]] | None = None

# Lock for thread-safe cache operations
_kb_cache_lock = threading.Lock()


def _get_bedrock_client():
    """Get or create Bedrock runtime client.

    Returns:
        Bedrock runtime client instance.

    Raises:
        RuntimeError: If AWS credentials are not configured properly.
    """
    global _bedrock_client
    if _bedrock_client is None:
        try:
            _bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=os.environ.get("AWS_REGION", "us-west-2"),
            )
            logger.debug("Bedrock client created successfully")
        except NoCredentialsError as e:
            logger.error("AWS credentials not found")
            raise RuntimeError(
                "AWS credentials not configured. "
                "Please run 'aws configure' or set environment variables."
            ) from e
        except ClientError as e:
            logger.error(f"Failed to create Bedrock client: {e}")
            raise RuntimeError(
                "Failed to initialize AWS Bedrock client. "
                "Please check your AWS configuration."
            ) from e
    return _bedrock_client


def _get_embeddings(
    texts: list[str], input_type: str = "search_document"
) -> NDArray[np.float32]:
    """Get embeddings for a list of texts using Cohere Embed.

    Args:
        texts: List of texts to embed.
        input_type: Type of input - "search_document" for indexing,
                   "search_query" for queries.

    Returns:
        Numpy array of embeddings with shape (len(texts), embedding_dim).

    Raises:
        RuntimeError: If embedding generation fails.
    """
    client = _get_bedrock_client()

    body = json.dumps(
        {
            "texts": texts,
            "input_type": input_type,
        }
    )

    try:
        response = client.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            body=body,
        )
        response_body = json.loads(response["body"].read())
        embeddings = response_body["embeddings"]
        logger.debug(f"Generated embeddings for {len(texts)} texts")
        return np.array(embeddings, dtype=np.float32)
    except ClientError as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise RuntimeError(
            "Failed to generate embeddings. Please check your AWS permissions."
        ) from e


def _cosine_similarity(
    query_embedding: NDArray[np.float32],
    doc_embeddings: NDArray[np.float32],
) -> NDArray[np.float32]:
    """Calculate cosine similarity between query and documents.

    Args:
        query_embedding: Query embedding with shape (embedding_dim,).
        doc_embeddings: Document embeddings with shape (num_docs, embedding_dim).

    Returns:
        Similarity scores with shape (num_docs,).
    """
    # Normalize vectors
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    doc_norms = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)

    # Calculate cosine similarity
    similarities = np.dot(doc_norms, query_norm)

    return similarities


def _load_knowledge_base(knowledge_dir: Path) -> list[dict[str, str]]:
    """Load all markdown files from the knowledge directory.

    Args:
        knowledge_dir: Path to the knowledge directory.

    Returns:
        List of sections with title and content.
    """
    sections: list[dict[str, str]] = []
    md_files = list(knowledge_dir.glob("*.md"))
    logger.info(f"Loading knowledge base from {len(md_files)} markdown files")

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read file {md_file.name}: {e}")
            continue

        current_section = ""
        current_content: list[str] = []

        for line in content.split("\n"):
            if line.startswith("## ") or line.startswith("### "):
                if current_section and current_content:
                    sections.append(
                        {
                            "title": current_section,
                            "content": "\n".join(current_content).strip(),
                        }
                    )
                current_section = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_section and current_content:
            sections.append(
                {
                    "title": current_section,
                    "content": "\n".join(current_content).strip(),
                }
            )

    logger.info(f"Loaded {len(sections)} sections from knowledge base")
    return sections


def _build_knowledge_base_index(
    knowledge_dir: Path,
) -> tuple[list[dict[str, str]], NDArray[np.float32]]:
    """Build or retrieve cached knowledge base index.

    Args:
        knowledge_dir: Path to the knowledge directory.

    Returns:
        Tuple of (sections, embeddings).
    """
    global _kb_cache

    cache_key = str(knowledge_dir)

    # Fast path: already cached (no lock needed for read check)
    if _kb_cache is not None and cache_key in _kb_cache:
        return _kb_cache[cache_key]

    # Slow path: acquire lock and build
    with _kb_cache_lock:
        # Double-check after acquiring lock
        if _kb_cache is not None and cache_key in _kb_cache:
            return _kb_cache[cache_key]

        sections = _load_knowledge_base(knowledge_dir)

        if not sections:
            return [], np.array([], dtype=np.float32)

        # Create text for embedding: combine title and content
        texts = [f"{s['title']}: {s['content']}" for s in sections]

        # Get embeddings for all sections
        embeddings = _get_embeddings(texts, input_type="search_document")

        _kb_cache = {cache_key: (sections, embeddings)}

        return sections, embeddings


def _search_sections(
    sections: list[dict[str, str]],
    embeddings: NDArray[np.float32],
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    min_score: float = DEFAULT_MIN_SIMILARITY_SCORE,
) -> list[dict[str, str | float]]:
    """Search sections using semantic similarity.

    Args:
        sections: List of sections with title and content.
        embeddings: Embeddings for all sections.
        query: Search query string.
        max_results: Maximum number of results to return.
        min_score: Minimum similarity score to include in results.

    Returns:
        List of matching sections with title, content, and score.
    """
    if len(sections) == 0:
        return []

    # Get query embedding
    query_embedding = _get_embeddings([query], input_type="search_query")[0]

    # Calculate similarities
    similarities = _cosine_similarity(query_embedding, embeddings)

    # Get top results
    top_indices = np.argsort(similarities)[::-1][:max_results]

    results = []
    for idx in top_indices:
        score = float(similarities[idx])
        if score >= min_score:
            results.append(
                {
                    "title": sections[idx]["title"],
                    "content": sections[idx]["content"],
                    "score": score,
                }
            )

    return results


# Default knowledge directory path
_KNOWLEDGE_DIR: Path | None = None


def set_knowledge_directory(path: Path | str) -> None:
    """Set the knowledge directory path.

    Args:
        path: Path to the knowledge directory.
    """
    global _KNOWLEDGE_DIR, _kb_cache
    _KNOWLEDGE_DIR = Path(path)
    # Clear cache when directory changes
    _kb_cache = None


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
    to answer customer questions accurately. Uses semantic search for better
    understanding of query intent.

    Args:
        query: The search query describing what information to find.
            Examples: "返品ポリシー", "配送時間", "パスワード リセット"

    Returns:
        Relevant information from the knowledge base, or a message if no
        results are found.
    """
    logger.debug(f"Searching knowledge base for: {query}")

    try:
        knowledge_dir = get_knowledge_directory()
    except ValueError as e:
        logger.error(f"Knowledge directory not configured: {e}")
        return "ナレッジベースの設定に問題があります。管理者にお問い合わせください。"

    if not knowledge_dir.exists():
        logger.error(f"Knowledge directory not found: {knowledge_dir}")
        return "ナレッジベースを読み込めませんでした。管理者にお問い合わせください。"

    try:
        sections, embeddings = _build_knowledge_base_index(knowledge_dir)
    except RuntimeError as e:
        logger.error(f"Failed to build knowledge base index: {e}")
        return (
            "ナレッジベースの検索中にエラーが発生しました。"
            "しばらく経ってから再度お試しください。"
        )

    if not sections:
        logger.warning("No knowledge base content found")
        return "ナレッジベースにコンテンツが見つかりません。"

    try:
        results = _search_sections(sections, embeddings, query)
    except RuntimeError as e:
        logger.error(f"Failed to search knowledge base: {e}")
        return "検索中にエラーが発生しました。しばらく経ってから再度お試しください。"

    if not results:
        logger.info(f"No relevant information found for query: {query}")
        return f"「{query}」に関連する情報が見つかりませんでした。"

    logger.info(f"Found {len(results)} results for query: {query}")

    # Format results
    output_parts = ["## 検索結果\n"]
    for i, result in enumerate(results, 1):
        score = result["score"]
        output_parts.append(f"### {i}. {result['title']} (関連度: {score:.2f})\n")
        output_parts.append(str(result["content"]))
        output_parts.append("\n")

    return "\n".join(output_parts)
