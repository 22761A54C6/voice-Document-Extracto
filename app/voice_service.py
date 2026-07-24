import logging
from faster_whisper import WhisperModel
from fastapi import HTTPException

from app.config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

logger = logging.getLogger(__name__)


# Loaded once at import time (module-level singleton), reused across requests.
# First run downloads the model to the faster-whisper cache dir (~/.cache/huggingface).
logger.info(f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}' "
            f"(device={WHISPER_DEVICE}, compute_type={WHISPER_COMPUTE_TYPE})...")
_model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
logger.info("Whisper model loaded")


def transcribe_audio(input_path: str) -> str:
    try:
        segments, info = _model.transcribe(input_path, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Audio transcription failed: {e}")