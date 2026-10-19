"""Fixed values used across the service.

Settings that change between environments (keys, hosts, limits, timeouts) live in
app/core/config.py and come from .env. Everything here is part of how the service
works and only changes together with the code.
"""

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
SERVICE_NAME = "voice-ai-service"
APP_TITLE = "Voice AI Extraction Service"

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
ROUTE_VOICE = "/voice"
ROUTE_HEALTH = "/health"
ROUTE_TEST_UI = "/voice-products-extract-using-ai"
ROUTE_FAVICON = "/favicon.ico"

# Requests to these paths are not written to the request log (probes, favicon)
QUIET_PATHS = (ROUTE_HEALTH, ROUTE_FAVICON)

# ---------------------------------------------------------------------------
# HTTP headers and the test UI
# ---------------------------------------------------------------------------
TRACE_ID_HEADER = "X-Trace-Id"
SPAN_ID_HEADER = "X-Span-Id"
# Set by the API gateway ("/api"); empty when the service is called directly
API_PREFIX_HEADER = "X-Api-Prefix"
# Placeholder in static/test_ui.html replaced with the API prefix
API_PREFIX_PLACEHOLDER = "__API_PREFIX__"
STATIC_DIR_NAME = "static"
TEST_UI_FILE = "test_ui.html"

SSE_MEDIA_TYPE = "text/event-stream"
# Stop proxies (nginx, gateways) from buffering or caching the progress stream
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
# Send a comment this often so proxies don't drop a quiet SSE connection
SSE_KEEPALIVE_SECONDS = 30.0
SSE_KEEPALIVE_COMMENT = ": keepalive\n\n"

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
BYTES_PER_MB = 1024 * 1024
ALLOWED_AUDIO_CONTENT_TYPES = {
    # Most common
    "audio/mpeg", "audio/mp3",           # MP3
    "audio/wav", "audio/x-wav",          # WAV
    "audio/m4a", "audio/x-m4a",          # M4A
    "audio/mp4",                         # M4A as sent by Safari/iOS recorders
    "audio/aac",                         # AAC
    # Web formats
    "audio/ogg",                         # OGG
    "audio/webm",                        # WebM (Chrome/Firefox recorders)
    "audio/opus",                        # Opus
    # Lossless / legacy
    "audio/flac", "audio/x-flac",        # FLAC
    "audio/aiff", "audio/x-aiff",        # AIFF
    "audio/x-ms-wma", "audio/wma",       # WMA
    # Mobile
    "audio/amr", "audio/x-amr",          # AMR
    "audio/3gpp", "audio/3gpp2",         # 3GPP
}

# Stored in products.sourceType and returned in the result
SOURCE_AUDIO = "audio"

# ---------------------------------------------------------------------------
# SSE progress events: stage and percentage
# ---------------------------------------------------------------------------
STAGE_VALIDATION = "validation"
STAGE_UPLOAD = "upload"
STAGE_PREPROCESSING = "preprocessing"
STAGE_TRANSCRIPTION = "transcription"
STAGE_EXTRACTION = "extraction"
STAGE_EMBEDDING = "embedding"
STAGE_COMPLETE = "complete"
STAGE_ERROR = "error"

PROGRESS_VALIDATION = 5
PROGRESS_UPLOAD = 10
PROGRESS_PREPROCESSING = 15
PROGRESS_TRANSCRIPTION_STARTED = 20
PROGRESS_TRANSCRIPTION_DONE = 50
PROGRESS_EXTRACTION_STARTED = 55
PROGRESS_EXTRACTION_DONE = 75
PROGRESS_EMBEDDING_STARTED = 80
PROGRESS_EMBEDDING_DONE = 90
PROGRESS_COMPLETE = 100
PROGRESS_ERROR = 0

MILLISECONDS_PER_SECOND = 1000

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
PRODUCTS_COLLECTION = "products"
CATEGORIES_COLLECTION = "categories"
# Give up on an unreachable server after 5 s instead of the 30 s driver default
MONGO_SERVER_SELECTION_TIMEOUT_MS = 5000

# ---------------------------------------------------------------------------
# Category vector search (index created by the Image-Text-Pdf service's category sync)
# ---------------------------------------------------------------------------
VECTOR_INDEX_NAME = "category_vector_index"
VECTOR_FIELD = "embedding"
# Must match the vectors in the shared categories collection
EMBED_DIMENSIONS = 768
# Only the best match is used
VECTOR_SEARCH_TOP_K = 1

# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
JSON_MIME_TYPE = "application/json"
# Must match how the Image-Text-Pdf service embeds categories
EMBED_TASK_TYPE = "SEMANTIC_SIMILARITY"
# gemini-embedding-001 accepts at most 100 texts per request
EMBED_BATCH_SIZE = 100
# /health gives Gemini this long to answer
GEMINI_HEALTH_TIMEOUT_MS = 5000

MAX_LLM_ATTEMPTS = 3
# Wait 1 s, then 2 s, ... between attempts
RETRY_BACKOFF_BASE_SECONDS = 1
# Matched against the Gemini error text
RETRYABLE_ERROR_MARKERS = ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded")

# Output token budget: JSON is wordier than speech, so about 1.2 tokens per transcript character
LLM_OUTPUT_TOKENS_PER_CHAR = 1.2
LLM_MIN_OUTPUT_TOKENS = 1000
LLM_MAX_OUTPUT_TOKENS = 8192

# Markdown code fence the LLM sometimes wraps JSON in
MARKDOWN_FENCE = "```"

# ---------------------------------------------------------------------------
# Product defaults (used when the LLM leaves a field out)
# ---------------------------------------------------------------------------
DEFAULT_PRICE = 0.0
DEFAULT_QUANTITY = 0
DEFAULT_PREPARATION_TIME = 0
DEFAULT_DESCRIPTION = ""

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
HEALTH_OK = "ok"
HEALTH_ERROR = "error"
HEALTH_DEGRADED = "degraded"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LINE_FORMAT = "%(asctime)s %(levelname)-7s %(trace)s%(span)s%(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_JSON_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
LOG_FORMAT_JSON = "json"
# At this level stack traces include library frames too
LOG_LEVEL_DEBUG = "DEBUG"
# Longest error text copied into a log line
LOG_ERROR_MAX_CHARS = 200
# Longest unparseable LLM reply copied into a DEBUG log line
LOG_LLM_REPLY_MAX_CHARS = 500
# Libraries that log every HTTP call / internal step at INFO
NOISY_LOGGERS = ("httpx", "httpcore", "google_genai", "pymongo", "urllib3", "multipart", "huggingface_hub")
FASTER_WHISPER_LOGGER = "faster_whisper"
