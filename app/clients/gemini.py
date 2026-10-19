import logging
from typing import List, Optional

from google import genai
from google.genai import types

from app.core.config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_EMBED_MODEL,
    GEMINI_THINKING_LEVEL, GEMINI_THINKING_BUDGET, GEMINI_TIMEOUT_MS,
)
from app.core.constants import EMBED_BATCH_SIZE, EMBED_DIMENSIONS, EMBED_TASK_TYPE, GEMINI_HEALTH_TIMEOUT_MS
from app.core.messages import MISSING_ENV_VAR

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None


def get_client() -> genai.Client:
    """Created lazily so the service can still start (and serve /health) without a key."""
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(MISSING_ENV_VAR.format(name="GEMINI_API_KEY"))
        _client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
    return _client


def thinking_config() -> types.ThinkingConfig:
    if GEMINI_THINKING_BUDGET is not None:
        return types.ThinkingConfig(thinking_budget=GEMINI_THINKING_BUDGET)
    return types.ThinkingConfig(thinking_level=GEMINI_THINKING_LEVEL)


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts using Gemini (in batches of EMBED_BATCH_SIZE)."""
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        result = await get_client().aio.models.embed_content(
            model=GEMINI_EMBED_MODEL,
            contents=texts[i:i + EMBED_BATCH_SIZE],
            config=types.EmbedContentConfig(
                task_type=EMBED_TASK_TYPE,
                output_dimensionality=EMBED_DIMENSIONS,
            ),
        )
        embeddings.extend(e.values for e in result.embeddings)

    logger.debug(f"Gemini embed: {len(embeddings)} embeddings")
    return embeddings


def check_connection() -> None:
    """Raise if Gemini is unreachable or the key is invalid (used by /health)."""
    get_client().models.get(
        model=GEMINI_MODEL,
        # Short timeout so /health doesn't hang for the full request timeout
        config=types.GetModelConfig(http_options=types.HttpOptions(timeout=GEMINI_HEALTH_TIMEOUT_MS)),
    )
