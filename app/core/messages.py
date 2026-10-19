"""Messages returned to API clients (HTTP error details and SSE progress/error events).

Templates with {placeholders} are filled with str.format().
"""

# ---------------------------------------------------------------------------
# Upload validation (HTTP 400)
# ---------------------------------------------------------------------------
UNSUPPORTED_FILE_TYPE = "Unsupported file type: {content_type}. Allowed: {allowed}"
EMPTY_FILE = "Uploaded file is empty"
FILE_TOO_LARGE = "File too large (max {max_mb:g}MB)"

# ---------------------------------------------------------------------------
# Progress (SSE)
# ---------------------------------------------------------------------------
VALIDATING = "Validating file type and size"
READING_UPLOAD = "Reading uploaded file"
PREPARING_AUDIO = "Preparing audio"
TRANSCRIPTION_STARTED = "Starting audio transcription"
TRANSCRIPTION_DONE = "Audio transcription completed"
EXTRACTION_STARTED = "Starting LLM product extraction"
EXTRACTION_DONE = "LLM product extraction completed"
EMBEDDING_STARTED = "Generating embeddings and storing in database"
EMBEDDING_DONE = "Embeddings generated and stored"
PROCESSING_COMPLETE = "Processing completed successfully"

# ---------------------------------------------------------------------------
# Errors (SSE error events)
# ---------------------------------------------------------------------------
NO_SPEECH = "No speech detected in audio"
TRANSCRIPTION_FAILED = "Audio transcription failed. Please try again."
EXTRACTION_FAILED = "Product extraction failed. Please try again."
NO_PRODUCTS = "No products could be extracted from this audio"
STORE_FAILED = "Failed to store products. Please try again."
EMBEDDING_FAILED = "Embedding generation failed. Please try again."
EMBEDDING_COUNT_MISMATCH = "Embedding generation failed due to count mismatch"
CATEGORY_SEARCH_FAILED = "Category search failed. Please try again."
PROCESSING_FAILED = "Processing failed. Please try again."

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
MONGODB_OK = "MongoDB connection successful"
MONGODB_FAILED = "MongoDB connection failed: {error}"
GEMINI_OK = "Gemini API reachable"
GEMINI_FAILED = "Gemini connection failed: {error}"
WHISPER_OK = "Whisper model loaded"
WHISPER_NOT_LOADED = "Whisper model not loaded"

# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------
UNEXPECTED_ERROR = "An unexpected error occurred. Please try again."
TEST_UI_NOT_FOUND = "<h1>UI not found</h1>"
MISSING_ENV_VAR = "{name} is not set -- add it to your .env file"
MISSING_ENV_VARS = "Missing required environment variables: {names} -- set them in your .env file or environment before starting the service."
