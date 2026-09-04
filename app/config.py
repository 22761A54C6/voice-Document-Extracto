import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.environ.get("PORT", 6003))
HOST = os.environ.get("HOST", "localhost")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_EMBED_MODEL = "gemini-embedding-001"
GEMINI_EMBED_DIMENSIONS = 512
GEMINI_TEXT_MODEL = "gemini-3.6-flash"
# GEMINI_TEXT_MODEL = "gemini-2.5-flash-lite"

# Same Mongo cluster + database as AI-service-Ai -- shared "products" and
# "categories" collections, so both services write into the same place.
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "bizlink_gemini")

ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/m4a", "audio/mp4", "audio/ogg", "audio/webm",
    "audio/x-m4a", "audio/aac",
}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

# faster-whisper model settings
# WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base.en")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# Ollama LLM settings
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
