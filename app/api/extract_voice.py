import json
import uuid
import logging
import time
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse

from app.core import messages
from app.core.config import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from app.core.constants import (
    ALLOWED_AUDIO_CONTENT_TYPES, MILLISECONDS_PER_SECOND, SOURCE_AUDIO, ROUTE_VOICE,
    SSE_MEDIA_TYPE, SSE_HEADERS, SSE_KEEPALIVE_SECONDS, SSE_KEEPALIVE_COMMENT,
    STAGE_VALIDATION, STAGE_UPLOAD, STAGE_PREPROCESSING, STAGE_TRANSCRIPTION, STAGE_EXTRACTION,
    STAGE_EMBEDDING, STAGE_COMPLETE, STAGE_ERROR,
    PROGRESS_VALIDATION, PROGRESS_UPLOAD, PROGRESS_PREPROCESSING,
    PROGRESS_TRANSCRIPTION_STARTED, PROGRESS_TRANSCRIPTION_DONE,
    PROGRESS_EXTRACTION_STARTED, PROGRESS_EXTRACTION_DONE,
    PROGRESS_EMBEDDING_STARTED, PROGRESS_EMBEDDING_DONE, PROGRESS_COMPLETE, PROGRESS_ERROR,
)
from app.pipeline.transcription import transcribe_audio
from app.pipeline.product_extraction import extract_products_with_llm
from app.pipeline.product_normalizer import normalize_products
from app.pipeline.product_storage import embed_and_store
from app.api.schemas import ProgressEvent
from app.core.logging import root_cause

logger = logging.getLogger(__name__)

router = APIRouter()


def _elapsed_ms(since: float) -> float:
    return (time.time() - since) * MILLISECONDS_PER_SECOND


@router.post(ROUTE_VOICE)
async def extract_voice(
    file: UploadFile = File(...)
):
    """
    Voice extraction endpoint with SSE streaming for progress updates.
    Invalid uploads are rejected with a 400 before streaming starts; after that
    every outcome (progress, error, final result) is an SSE event.
    """
    # Validate before streaming so the client gets a proper HTTP error
    if file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=messages.UNSUPPORTED_FILE_TYPE.format(content_type=file.content_type, allowed=sorted(ALLOWED_AUDIO_CONTENT_TYPES)),
        )
    file_read_start = time.time()
    contents = await file.read()
    file_read_duration = _elapsed_ms(file_read_start)
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=messages.EMPTY_FILE)
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=messages.FILE_TOO_LARGE.format(max_mb=MAX_FILE_SIZE_MB))

    event_queue: asyncio.Queue = asyncio.Queue()
    # The task inherits this request's trace id (set by the request middleware)
    processing_task = asyncio.create_task(
        process_voice_with_progress(contents, file_read_duration, event_queue)
    )

    return StreamingResponse(
        progress_event_generator(event_queue, processing_task),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


async def send_progress(event_queue: asyncio.Queue, stage: str, progress: float, message: str):
    """Helper function to send progress events to the queue."""
    await event_queue.put(ProgressEvent(stage=stage, progress=progress, message=message, timestamp=time.time()))


async def process_voice_with_progress(contents: bytes, file_read_duration: float, event_queue: asyncio.Queue) -> None:
    """
    Transcribe -> extract products with the LLM -> embed, match categories and store.
    Every outcome is reported through event_queue: progress events, then either
    an "error" event or a "complete" event followed by the result dict.
    """
    endpoint_start = time.time()
    stage = STAGE_TRANSCRIPTION
    try:
        await send_progress(event_queue, STAGE_VALIDATION, PROGRESS_VALIDATION, messages.VALIDATING)
        await send_progress(event_queue, STAGE_UPLOAD, PROGRESS_UPLOAD, messages.READING_UPLOAD)
        await send_progress(event_queue, STAGE_PREPROCESSING, PROGRESS_PREPROCESSING, messages.PREPARING_AUDIO)

        # STEP 1: Transcribe Audio to Text
        await send_progress(event_queue, STAGE_TRANSCRIPTION, PROGRESS_TRANSCRIPTION_STARTED, messages.TRANSCRIPTION_STARTED)
        transcribe_start = time.time()
        raw_text, language, audio_seconds = await asyncio.to_thread(transcribe_audio, contents)
        transcribe_duration = _elapsed_ms(transcribe_start)
        logger.debug(f"Transcribed text: {raw_text!r}")
        await send_progress(event_queue, STAGE_TRANSCRIPTION, PROGRESS_TRANSCRIPTION_DONE, messages.TRANSCRIPTION_DONE)

        if not raw_text.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=messages.NO_SPEECH)

        # STEP 2: Extract Products with LLM
        stage = STAGE_EXTRACTION
        await send_progress(event_queue, STAGE_EXTRACTION, PROGRESS_EXTRACTION_STARTED, messages.EXTRACTION_STARTED)
        extract_start = time.time()
        products, token_usage = await extract_products_with_llm(raw_text)
        extract_duration = _elapsed_ms(extract_start)
        logger.debug(f"LLM extracted products: {json.dumps(products, ensure_ascii=False)}")
        await send_progress(event_queue, STAGE_EXTRACTION, PROGRESS_EXTRACTION_DONE, messages.EXTRACTION_DONE)

        # STEP 3: Normalize Product Data
        products = normalize_products(products)
        if not products:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=messages.NO_PRODUCTS)

        # STEP 4: Generate Embeddings and Store in MongoDB
        stage = STAGE_EMBEDDING
        await send_progress(event_queue, STAGE_EMBEDDING, PROGRESS_EMBEDDING_STARTED, messages.EMBEDDING_STARTED)
        batch_id = str(uuid.uuid4())
        embed_start = time.time()
        try:
            response_data = await embed_and_store(
                products,
                batch_id=batch_id,
                source_type=SOURCE_AUDIO,
                processing_time=time.time() - endpoint_start
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=messages.STORE_FAILED) from e
        embed_duration = _elapsed_ms(embed_start)
        await send_progress(event_queue, STAGE_EMBEDDING, PROGRESS_EMBEDDING_DONE, messages.EMBEDDING_DONE)

        # STEP 5: Build Response with Timing Metrics
        total_duration = _elapsed_ms(endpoint_start) + file_read_duration
        logger.info(f"voice: {len(products)} products in {total_duration / MILLISECONDS_PER_SECOND:.2f}s | "
                    f"audio={audio_seconds:.1f}s lang={language} "
                    f"transcription={transcribe_duration / MILLISECONDS_PER_SECOND:.2f}s "
                    f"llm={extract_duration / MILLISECONDS_PER_SECOND:.2f}s "
                    f"embedding+db={embed_duration / MILLISECONDS_PER_SECOND:.2f}s "
                    f"tokens={token_usage.get('total_tokens', 0)} batch={batch_id}")

        response_data["processingTime"] = total_duration / MILLISECONDS_PER_SECOND
        response_data["tokenUsage"] = token_usage
        response_data["timingBreakdown"] = {
            "fileRead_ms": file_read_duration,
            "transcription_ms": transcribe_duration,
            "llmExtraction_ms": extract_duration,
            "embeddingAndStorage_ms": embed_duration,
            "total_ms": total_duration
        }

        await send_progress(event_queue, STAGE_COMPLETE, PROGRESS_COMPLETE, messages.PROCESSING_COMPLETE)
        await event_queue.put(response_data)
    except Exception as e:
        elapsed = time.time() - endpoint_start
        if isinstance(e, HTTPException):
            message = e.detail
            cause = root_cause(e)
            reason = f" ({type(cause).__name__}: {cause})" if cause is not e else ""
            # Bad input (4xx) is the client's problem; 5xx means Gemini, MongoDB or the service failed
            level = logging.ERROR if e.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logging.WARNING
            logger.log(level, f"voice: failed at {stage} after {elapsed:.2f}s: {message}{reason}")
        else:
            message = messages.PROCESSING_FAILED
            logger.exception(f"voice: unexpected error at {stage} after {elapsed:.2f}s")
        await send_progress(event_queue, STAGE_ERROR, PROGRESS_ERROR, message)


async def progress_event_generator(event_queue: asyncio.Queue, processing_task: asyncio.Task) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE-formatted progress events, ending after the
    final result or an error. Cancels processing if the client disconnects.
    """
    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield SSE_KEEPALIVE_COMMENT
                continue

            # The final result is a plain dict; everything else is a ProgressEvent
            if isinstance(event, dict):
                yield f"data: {json.dumps(event)}\n\n"
                break

            yield f"data: {event.model_dump_json()}\n\n"
            if event.stage == STAGE_ERROR:
                break
    finally:
        if not processing_task.done():
            logger.warning("voice: client disconnected, processing cancelled")
            processing_task.cancel()
