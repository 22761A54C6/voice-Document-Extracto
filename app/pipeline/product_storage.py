import uuid
import logging
import asyncio
from typing import List

from fastapi import HTTPException, status

from app.core import messages
from app.core.constants import PRODUCTS_COLLECTION, SOURCE_AUDIO
from app.core.database import db
from app.core.logging import root_cause
from app.clients.gemini import get_embeddings_batch as gemini_get_embeddings_batch
from app.pipeline.category_matching import NO_MATCH, match_category

logger = logging.getLogger(__name__)


def _build_target_format_dict(product: dict) -> dict:
    """Target format for MongoDB and the API response (no embedding)."""
    return {
        "name": product["name"],
        "description": product["description"],
        "categoryId": product["matchedCategorySourceId"],
        "quantity": product["quantity"],
        "preparationTime": product["preparationTime"],
        "price": product["price"],
        "variants": product["variants"]
    }


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Embed product names with Gemini; failures become a 502."""
    if not texts:
        return []

    try:
        return await gemini_get_embeddings_batch(texts)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=messages.EMBEDDING_FAILED) from e


async def embed_and_store(products: List[dict], batch_id: str = None, source_type: str = SOURCE_AUDIO,
                          processing_time: float = 0.0) -> dict:
    if not products:
        return {"batchId": batch_id, "sourceType": source_type, "targetFormat": [], "processingTime": processing_time}

    raw_names = [p["name"] for p in products]

    # Let embedding failures propagate -- silently returning [] here previously
    # made callers believe storage succeeded with 0 products saved.
    embeddings = await get_embeddings_batch(raw_names)

    if len(embeddings) != len(raw_names):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=messages.EMBEDDING_COUNT_MISMATCH)

    # match_category does a blocking MongoDB Atlas vector-search call, so run
    # every product's lookup in a worker thread, concurrently. to_thread copies
    # the trace context into the thread.
    async def classify_one(product: dict, embedding: list) -> dict:
        try:
            classification = await asyncio.to_thread(match_category, embedding)
            logger.debug(f"Category match: {product['name']!r} -> {classification['matchedCategory']!r} ({classification['matchedCategoryScore']})")
        except Exception as e:
            # Keep the product without a category rather than dropping it
            logger.warning(f"Category matching failed for {product['name']!r}, saved without category: {root_cause(e)}")
            classification = NO_MATCH
        return {**product, "embedding": embedding, **classification}

    processed = await asyncio.gather(*(
        classify_one(product, embedding)
        for product, embedding in zip(products, embeddings, strict=True)
    ))

    # Full product records including embeddings and match details
    products_for_mongo = [
        {
            "id": str(uuid.uuid4()),
            "batchId": batch_id,
            "name": p["name"],
            "description": p["description"],
            "price": p["price"],
            "quantity": p["quantity"],
            "preparationTime": p["preparationTime"],
            "variants": p["variants"],
            "matchedCategory": p["matchedCategory"],
            "matchedCategorySourceId": p["matchedCategorySourceId"],
            "matchedCategoryScore": p["matchedCategoryScore"],
            "embedding": p["embedding"]
        }
        for p in processed
    ]
    target_format = [_build_target_format_dict(p) for p in processed]

    # MongoDB will auto-generate _id as ObjectId
    doc = {
        "batchId": batch_id,
        "sourceType": source_type,
        "products": products_for_mongo,
        "targetFormat": target_format,
        "processingTime": processing_time
    }

    await asyncio.to_thread(db[PRODUCTS_COLLECTION].insert_one, doc)
    logger.debug(f"Stored batch {batch_id} with {len(processed)} products")

    return {
        "batchId": batch_id,
        "sourceType": source_type,
        "targetFormat": target_format,
        "processingTime": processing_time
    }
