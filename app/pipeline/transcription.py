import io
import logging
import time
from faster_whisper import WhisperModel
from fastapi import HTTPException, status

from app.core.config import (
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_BEAM_SIZE,
    WHISPER_VAD_FILTER, WHISPER_CPU_THREADS, WHISPER_LANGUAGE,
)
from app.core.messages import TRANSCRIPTION_FAILED

logger = logging.getLogger(__name__)


# Loaded once at import time (module-level singleton), reused across requests.
# First run downloads the model to the faster-whisper cache dir (~/.cache/huggingface).
_load_start = time.time()
_model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE,
                      cpu_threads=WHISPER_CPU_THREADS)
logger.info(f"Whisper model '{WHISPER_MODEL_SIZE}' loaded in {time.time() - _load_start:.1f}s "
            f"(device={WHISPER_DEVICE}, compute_type={WHISPER_COMPUTE_TYPE}, threads={WHISPER_CPU_THREADS})")


def transcribe_audio(audio: bytes) -> tuple[str, str, float]:
    """Transcribe raw audio bytes (any format ffmpeg/PyAV can decode).

    Returns (text, detected language, audio duration in seconds).
    """
    try:
        segments, info = _model.transcribe(
            io.BytesIO(audio),
            beam_size=WHISPER_BEAM_SIZE,
            language=WHISPER_LANGUAGE,  # None = auto-detect language
            vad_filter=WHISPER_VAD_FILTER,  # Use voice activity detection to filter non-speech
            word_timestamps=False,
            without_timestamps=True,  # Only the text is used, so skip decoding timestamp tokens
            condition_on_previous_text=False  # Faster and avoids repetition loops on long audio
        )
        # segments is a lazy generator -- transcription actually runs here
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        logger.debug(f"Transcribed {info.duration:.1f}s of audio, language={info.language} "
                     f"({info.language_probability:.2f}), {len(text)} chars")
        return text, info.language, info.duration
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=TRANSCRIPTION_FAILED) from e
