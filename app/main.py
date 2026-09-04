import os
import tempfile
import json
import uuid
import logging
import time
from typing import List
from pydantic import BaseModel
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Body
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import HOST, PORT, ALLOWED_AUDIO_CONTENT_TYPES, MAX_FILE_SIZE_BYTES
from app.voice_service import transcribe_audio
from app.extraction import extract_products_with_llm
# from app.extraction import translate_to_english_with_gemini
from app.embeddings import embed_and_store
from app.models import Product
from app.database import db
from app.logging_config import configure_logging
from app.ollama_service import translate_to_english, correct_text, generate_short_description

logger = logging.getLogger(__name__)


class TextCorrectionRequest(BaseModel):
    text: str


class HTTPRequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"event:http_request method:{request.method} path:{request.url.path} "
            f"status_code:{response.status_code} duration_ms:{duration_ms:.2f}"
        )
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging()
    logger.info("Voice AI Extraction Service started")
    
    yield
    
    # Shutdown
    opensearch_handler = getattr(logging.getLogger(), 'opensearch_handler', None)
    if opensearch_handler:
        opensearch_handler.stop()


app = FastAPI(title="Voice AI Extraction Service", lifespan=lifespan)
app.add_middleware(HTTPRequestLoggingMiddleware)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)


@app.post("/voice")
async def extract_voice(file: UploadFile = File(...)):
    logger.info("Voice extract endpoint hit")

    if file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        logger.warning(f"Unsupported file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {sorted(ALLOWED_AUDIO_CONTENT_TYPES)}"
        )

    contents = await file.read()
    if not contents:
        logger.warning("Uploaded file is empty")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File too large: {len(contents)} bytes")
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    suffix = os.path.splitext(file.filename or "")[1] or ".mp3"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        raw_text = transcribe_audio(tmp_path)
        logger.info(f"Transcribed text: {raw_text!r}")

        if not raw_text.strip():
            logger.warning("No speech detected in audio")
            raise HTTPException(status_code=422, detail="No speech detected in audio")

        products = extract_products_with_llm(raw_text)
        logger.info(f"LLM extracted {len(products)} raw products: "
                    f"{json.dumps(products, ensure_ascii=False)}")

        normalized_products = []
        for p in products:
            if not isinstance(p, dict) or not p.get("name"):
                continue
            price = p.get("price")
            if not isinstance(price, (int, float)):
                price = 0.0
            normalized_products.append({"name": p["name"], "price": float(price)})

        products = normalized_products
        logger.info(f"{len(products)} products ready for processing: "
                    f"{json.dumps(products, ensure_ascii=False)}")

        if not products:
            logger.warning("No products could be extracted from audio")
            raise HTTPException(status_code=422, detail="No products could be extracted from this audio")

        batch_id = str(uuid.uuid4())

        logger.info(f"Sending {len(products)} products to embed_and_store/MongoDB")
        try:
            stored_docs = embed_and_store(products, batch_id=batch_id)
            logger.info(f"embed_and_store stored {len(stored_docs)} of {len(products)} products")
        except Exception as e:
            logger.error(f"embed_and_store FAILED: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store products: {e}")

        for p in products:
            p["batchId"] = batch_id

        logger.info(f"Successfully processed voice extraction for batch_id: {batch_id}")
        return {
            "batchId": batch_id,
            "products": products
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/products/voice/{batch_id}", response_model=List[Product])
def get_voice_products_by_batch(batch_id: str):
    logger.info(f"Fetching products for batch_id: {batch_id}")
    docs = db.products.find({"batchId": batch_id}, {"embedding": 0})

    products = []
    for doc in docs:
        products.append({
            "id": doc["_id"],
            "batchId": doc.get("batchId"),
            "name": doc.get("name"),
            "price": doc.get("price", 0.0),
            "matchedCategory": doc.get("matchedCategory"),
            "matchedCategorySourceId": doc.get("matchedCategorySourceId"),
            "matchedCategoryScore": doc.get("matchedCategoryScore"),
            "matchStatus": doc.get("matchStatus"),
        })

    if not products:
        logger.warning(f"No products found for batch_id: {batch_id}")
        raise HTTPException(status_code=404, detail=f"No products found for batchId '{batch_id}'")

    logger.info(f"Successfully retrieved {len(products)} products for batch_id: {batch_id}")
    return products


@app.post("/correct-voice")
async def correct_voice(file: UploadFile = File(...)):
    logger.info("Voice correct endpoint hit")

    if file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        logger.warning(f"Unsupported file type: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {sorted(ALLOWED_AUDIO_CONTENT_TYPES)}"
        )

    contents = await file.read()
    if not contents:
        logger.warning("Uploaded file is empty")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File too large: {len(contents)} bytes")
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    suffix = os.path.splitext(file.filename or "")[1] or ".mp3"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        raw_text = transcribe_audio(tmp_path)
        logger.info(f"Transcribed text: {raw_text!r}")

        if not raw_text.strip():
            logger.warning("No speech detected in audio")
            raise HTTPException(status_code=422, detail="No speech detected in audio")

        translated_text = translate_to_english(raw_text)
        # translated_text = translate_to_english_with_gemini(raw_text)
        logger.info(f"Translated text: {translated_text!r}")

        short_description = generate_short_description(translated_text)
        logger.info(f"Short description: {short_description!r}")

        logger.info("Successfully processed voice translation")
        return {
            "original_text": raw_text,
            "corrected_text": translated_text,
            "short_description": short_description
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/correct-text")
async def correct_text_endpoint(request: TextCorrectionRequest):
    logger.info("Text correction endpoint hit")
    
    if not request.text or not request.text.strip():
        logger.warning("Empty text provided")
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    try:
        corrected_text = correct_text(request.text)
        logger.info(f"Corrected text: {corrected_text!r}")
        
        short_description = generate_short_description(corrected_text)
        logger.info(f"Short description: {short_description!r}")
        
        logger.info("Successfully processed text correction")
        return {
            "original_text": request.text,
            "corrected_text": corrected_text,
            "short_description": short_description
        }
    except Exception as e:
        logger.error(f"Text correction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text correction failed: {e}")


@app.get("/health")
def health():
    logger.info("Health check endpoint called")
    return {"status": "ok"}