"""Common model factory for Bedrock models.

This module provides a centralized factory for creating Bedrock model instances,
ensuring consistent configuration and thread-safe initialization.
"""

import logging
import threading
from enum import Enum

from strands.models.bedrock import BedrockModel

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Available model types for the application."""

    SONNET = "sonnet"
    HAIKU = "haiku"


# Model IDs for each model type
MODEL_IDS = {
    ModelType.SONNET: "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    ModelType.HAIKU: "global.anthropic.claude-haiku-4-5-20251001-v1:0",
}

# Cache for model instances (for singleton pattern)
_model_cache: dict[ModelType, BedrockModel] = {}
_model_cache_lock = threading.Lock()


def create_bedrock_model(model_type: ModelType) -> BedrockModel:
    """Create a new Bedrock model instance.

    Creates a fresh model instance each time. Use get_shared_model() for
    singleton instances.

    Args:
        model_type: The type of model to create (SONNET or HAIKU).

    Returns:
        A new BedrockModel instance.

    Raises:
        ValueError: If an unknown model type is provided.
    """
    if model_type not in MODEL_IDS:
        raise ValueError(f"Unknown model type: {model_type}")

    model_id = MODEL_IDS[model_type]
    logger.debug(f"Creating new Bedrock model: {model_type.value} ({model_id})")
    return BedrockModel(model_id=model_id)


def get_shared_model(model_type: ModelType) -> BedrockModel:
    """Get a shared (singleton) Bedrock model instance.

    Returns the same model instance for repeated calls with the same model type.
    Thread-safe initialization using double-checked locking.

    Args:
        model_type: The type of model to get (SONNET or HAIKU).

    Returns:
        A shared BedrockModel instance.

    Raises:
        ValueError: If an unknown model type is provided.
    """
    if model_type not in MODEL_IDS:
        raise ValueError(f"Unknown model type: {model_type}")

    # Fast path: already cached
    if model_type in _model_cache:
        return _model_cache[model_type]

    # Slow path: acquire lock and initialize
    with _model_cache_lock:
        # Double-check after acquiring lock
        if model_type not in _model_cache:
            _model_cache[model_type] = create_bedrock_model(model_type)
            logger.info(f"Initialized shared model: {model_type.value}")

        return _model_cache[model_type]


def clear_model_cache() -> None:
    """Clear the model cache.

    Useful for testing or when model configuration needs to be reset.
    """
    global _model_cache
    with _model_cache_lock:
        _model_cache = {}
        logger.debug("Model cache cleared")
