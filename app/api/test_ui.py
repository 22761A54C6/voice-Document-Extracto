import logging
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse

from app.core.constants import API_PREFIX_HEADER, API_PREFIX_PLACEHOLDER, ROUTE_TEST_UI, STATIC_DIR_NAME, TEST_UI_FILE
from app.core.messages import TEST_UI_NOT_FOUND

logger = logging.getLogger(__name__)

router = APIRouter()

PROJECT_ROOT = Path(__file__).parent.parent.parent
UI_PATH = PROJECT_ROOT / STATIC_DIR_NAME / TEST_UI_FILE


@router.get(ROUTE_TEST_UI, response_class=HTMLResponse)
async def serve_ui(request: Request) -> HTMLResponse:
    """Serve the voice extractor UI."""
    try:
        with open(UI_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        # Behind the gateway X-Api-Prefix is "/api"; direct access -> ""
        prefix = request.headers.get(API_PREFIX_HEADER, "")
        return HTMLResponse(content=html_content.replace(API_PREFIX_PLACEHOLDER, prefix))
    except FileNotFoundError:
        logger.error(f"UI file not found at {UI_PATH}")
        return HTMLResponse(content=TEST_UI_NOT_FOUND, status_code=status.HTTP_404_NOT_FOUND)
