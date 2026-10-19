"""Settings read from the environment (.env). Fixed values are in app/core/constants.py."""
import logging
import os
import sys
from dotenv import load_dotenv

from app.core.constants import BYTES_PER_MB
from app.core.messages import MISSING_ENV_VARS

load_dotenv()

# Server
PORT = int(os.getenv("PORT", "8002"))
HOST = os.getenv("HOST", "0.0.0.0")
# Auto-reload on code changes (development only)
RELOAD = os.getenv("RELOAD", "false").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # text | json
FASTER_WHISPER_LOG_LEVEL = os.getenv("FASTER_WHISPER_LOG_LEVEL", "WARNING")

# Same Mongo cluster + database as the Image-Text-Pdf service -- shared "products" and
# "categories" collections, so both services write into the same place.
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "bizlink_ollama")

# Upload limit
MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "5"))
MAX_FILE_SIZE_BYTES = int(MAX_FILE_SIZE_MB * BYTES_PER_MB)

# faster-whisper model
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
WHISPER_VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "true").lower() == "true"
# Defaults to all CPU cores; 0 lets CTranslate2 pick (4 threads)
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", str(os.cpu_count() or 0)))
# Skip language detection when the spoken language is known (e.g. "en"); empty = auto-detect
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE") or None

# Gemini (LLM + embeddings)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))
# Thinking adds latency and isn't needed for extraction. Gemini 3.x "lite" models take a
# thinking level ("minimal" is fastest); models that reject levels (e.g. gemini-3.8-flash)
# take GEMINI_THINKING_BUDGET=0 instead, which overrides the level when set.
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "minimal")
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET")) if os.getenv("GEMINI_THINKING_BUDGET") else None
GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "120000"))

# Vector search
VECTOR_SEARCH_NUM_CANDIDATES = int(os.getenv("VECTOR_SEARCH_NUM_CANDIDATES", "768"))

REQUIRED_ENV_VARS = {"MONGO_URI": MONGO_URI}


def validate_required_env_vars() -> None:
    """Exit with a clear message when a required setting is missing."""
    missing_vars = [name for name, value in REQUIRED_ENV_VARS.items() if not value]
    if missing_vars:
        logging.getLogger(__name__).critical(MISSING_ENV_VARS.format(names=", ".join(missing_vars)))
        sys.exit(1)
