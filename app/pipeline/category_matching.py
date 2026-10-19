from fastapi import HTTPException, status

from app.core.config import VECTOR_SEARCH_NUM_CANDIDATES
from app.core.constants import CATEGORIES_COLLECTION, VECTOR_FIELD, VECTOR_INDEX_NAME, VECTOR_SEARCH_TOP_K
from app.core.database import db
from app.core.messages import CATEGORY_SEARCH_FAILED

NO_MATCH = {"matchedCategory": None, "matchedCategorySourceId": None, "matchedCategoryScore": None}


def find_nearest_category(product_embedding: list[float], top_k: int = VECTOR_SEARCH_TOP_K) -> list[dict]:
    """Runs MongoDB Atlas Vector Search to find the closest category
    to a given product embedding. Returns matches with similarity scores.
    """
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": VECTOR_FIELD,
                "queryVector": product_embedding,
                "numCandidates": VECTOR_SEARCH_NUM_CANDIDATES,
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "sourceId": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    try:
        return list(db[CATEGORIES_COLLECTION].aggregate(pipeline))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=CATEGORY_SEARCH_FAILED) from e


def match_category(product_embedding: list[float]) -> dict:
    """Best-matching category for a product embedding (all None when nothing matches)."""
    matches = find_nearest_category(product_embedding)
    if not matches:
        return dict(NO_MATCH)
    top = matches[0]
    return {
        "matchedCategory": top["name"],
        "matchedCategorySourceId": top["sourceId"],
        "matchedCategoryScore": top["score"],
    }
