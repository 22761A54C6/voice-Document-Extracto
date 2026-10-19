"""Product extraction: prompt, Gemini call with retries, and JSON parsing."""
import asyncio
import json
import logging
from typing import List

from fastapi import HTTPException, status
from google.genai import types

from app.clients.gemini import get_client, thinking_config
from app.core.config import GEMINI_MODEL, GEMINI_TEMPERATURE
from app.core.constants import (
    JSON_MIME_TYPE, MAX_LLM_ATTEMPTS, RETRY_BACKOFF_BASE_SECONDS, RETRYABLE_ERROR_MARKERS,
    LLM_OUTPUT_TOKENS_PER_CHAR, LLM_MIN_OUTPUT_TOKENS, LLM_MAX_OUTPUT_TOKENS,
    MARKDOWN_FENCE, LOG_ERROR_MAX_CHARS, LOG_LLM_REPLY_MAX_CHARS,
)
from app.core.messages import EXTRACTION_FAILED
from app.pipeline.prompts import PRODUCT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def max_output_tokens(raw_text: str) -> int:
    """Output tokens to allow: JSON output is more verbose than the input, especially with variants."""
    return min(LLM_MAX_OUTPUT_TOKENS, max(LLM_MIN_OUTPUT_TOKENS, int(len(raw_text) * LLM_OUTPUT_TOKENS_PER_CHAR)))


def parse_products(text_out: str) -> List[dict]:
    """Parse the LLM's JSON reply into a product list.

    Raises ValueError when the reply isn't JSON in the expected shape.
    """
    text_out = text_out.strip()
    # Strip markdown code blocks if present
    if text_out.startswith(MARKDOWN_FENCE):
        text_out = text_out.split("\n", 1)[-1]
    if text_out.endswith(MARKDOWN_FENCE):
        text_out = text_out[:-len(MARKDOWN_FENCE)]

    parsed = json.loads(text_out.strip())
    # Handle both formats: direct array or wrapped in "products" key
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("products"), list):
        return parsed["products"]
    raise ValueError("Unexpected JSON structure")


async def _call_gemini(raw_text: str) -> tuple[List[dict], dict]:
    """
    Extract products from transcribed text using Gemini.

    Returns:
        Tuple of (product dicts with name, description, price, quantity, preparation_time and variants, token usage dict)
    """
    output_tokens = max_output_tokens(raw_text)
    logger.debug(f"LLM output budget: {output_tokens} tokens for {len(raw_text)} characters")

    response = None
    for attempt in range(MAX_LLM_ATTEMPTS):
        try:
            response = await get_client().aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=PRODUCT_EXTRACTION_PROMPT.format(text=raw_text),
                config=types.GenerateContentConfig(
                    temperature=GEMINI_TEMPERATURE,
                    max_output_tokens=output_tokens,
                    response_mime_type=JSON_MIME_TYPE,
                    thinking_config=thinking_config(),
                ),
            )
            break
        except Exception as e:
            if attempt < MAX_LLM_ATTEMPTS - 1 and any(m in str(e) for m in RETRYABLE_ERROR_MARKERS):
                wait = RETRY_BACKOFF_BASE_SECONDS * 2 ** attempt
                logger.warning(f"Gemini attempt {attempt + 1}/{MAX_LLM_ATTEMPTS} failed, retrying in {wait}s: {str(e)[:LOG_ERROR_MAX_CHARS]}")
                await asyncio.sleep(wait)
                continue
            raise Exception("LLM extraction request failed") from e

    text_out = response.text or ""
    usage = response.usage_metadata
    prompt_tokens = (usage.prompt_token_count or 0) if usage else 0
    completion_tokens = (usage.candidates_token_count or 0) if usage else 0
    logger.debug(f"Full LLM output: {text_out}")

    try:
        products = parse_products(text_out)
    except ValueError as e:  # json.JSONDecodeError is a ValueError
        logger.debug(f"Unparseable LLM output: {text_out[:LOG_LLM_REPLY_MAX_CHARS]}")
        raise Exception("Failed to parse JSON from LLM output") from e

    return products, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens
    }


async def extract_products_with_llm(raw_text: str) -> tuple[List[dict], dict]:
    """Extract products (name, description, price, quantity, preparation_time, variants). Returns (products, token_usage)."""
    try:
        return await _call_gemini(raw_text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=EXTRACTION_FAILED) from e
