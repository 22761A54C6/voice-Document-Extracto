import logging
from fastapi import APIRouter

from app.core import messages
from app.core.constants import HEALTH_OK, HEALTH_ERROR, HEALTH_DEGRADED, ROUTE_HEALTH
from app.clients.gemini import check_connection as check_gemini_connection
from app.core.database import db
from app.pipeline.transcription import _model

logger = logging.getLogger(__name__)

router = APIRouter()


def check_mongodb() -> dict:
    """Check MongoDB connectivity."""
    try:
        db.command("ping")
        return {"status": HEALTH_OK, "message": messages.MONGODB_OK}
    except Exception as e:
        logger.error(f"Health check: MongoDB unreachable: {e}")
        return {"status": HEALTH_ERROR, "message": messages.MONGODB_FAILED.format(error=e)}


def check_gemini() -> dict:
    """Check Gemini API connectivity and key validity."""
    try:
        check_gemini_connection()
        return {"status": HEALTH_OK, "message": messages.GEMINI_OK}
    except Exception as e:
        logger.error(f"Health check: Gemini unreachable: {e}")
        return {"status": HEALTH_ERROR, "message": messages.GEMINI_FAILED.format(error=e)}


def check_whisper_model() -> dict:
    """Check if Whisper model is loaded."""
    if _model is None:
        return {"status": HEALTH_ERROR, "message": messages.WHISPER_NOT_LOADED}
    return {"status": HEALTH_OK, "message": messages.WHISPER_OK}


@router.get(ROUTE_HEALTH)
def health() -> dict:
    """Health check endpoint with dependency checks."""
    checks = {
        "mongodb": check_mongodb(),
        "gemini": check_gemini(),
        "whisper_model": check_whisper_model(),
    }
    all_ok = all(check["status"] == HEALTH_OK for check in checks.values())
    return {
        "status": HEALTH_OK if all_ok else HEALTH_DEGRADED,
        "checks": checks,
    }
