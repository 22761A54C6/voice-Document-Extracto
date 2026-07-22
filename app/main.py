import os
import tempfile
import json
import uuid
import logging
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse

from app.config import HOST, PORT, ALLOWED_AUDIO_CONTENT_TYPES, MAX_FILE_SIZE_BYTES
from app.voice_service import transcribe_audio
from app.extraction import extract_products_with_llm
from app.embeddings import embed_and_store
from app.models import Product
from app.database import db

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Voice AI Extraction Service")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)


@app.post("/voice")
async def extract_voice(file: UploadFile = File(...)):
    print("!!!!!!!!!! VOICE EXTRACT ENDPOINT HIT !!!!!!!!!!")

    if file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {sorted(ALLOWED_AUDIO_CONTENT_TYPES)}"
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    suffix = os.path.splitext(file.filename or "")[1] or ".mp3"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        raw_text = transcribe_audio(tmp_path)
        print(f"[voice] transcribed text: {raw_text!r}")

        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="No speech detected in audio")

        products = extract_products_with_llm(raw_text)
        print(f"[voice] LLM extracted {len(products)} raw products: "
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
        print(f"[voice] {len(products)} products after normalization: "
              f"{json.dumps(products, ensure_ascii=False)}")

        if not products:
            raise HTTPException(status_code=422, detail="No products could be extracted from this audio")

        batch_id = str(uuid.uuid4())

        print(f"[voice] >>> SENDING {len(products)} PRODUCTS TO embed_and_store/MongoDB <<< batchId={batch_id}")
        try:
            stored_docs = embed_and_store(products, batch_id=batch_id)
            print(f"[voice] embed_and_store stored {len(stored_docs)} of {len(products)} products")
        except Exception as e:
            print(f"[voice] !!! embed_and_store FAILED: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store products: {e}")

        for p in products:
            p["batchId"] = batch_id

        return {
            "batchId": batch_id,
            "products": products
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/products/voice/{batch_id}", response_model=List[Product])
def get_voice_products_by_batch(batch_id: str):
    docs = db.products.find({"batchId": batch_id}, {"embedding": 0})

    products = []
    for doc in docs:
        products.append({
            "id": doc["_id"],
            "batchId": doc.get("batchId"),
            "name": doc.get("name"),
            "normalizedName": doc.get("normalizedName"),
            "price": doc.get("price"),
            "matchedCategory": doc.get("matchedCategory"),
            "matchedCategorySourceId": doc.get("matchedCategorySourceId"),
            "matchedCategoryScore": doc.get("matchedCategoryScore"),
            "matchStatus": doc.get("matchStatus"),
        })

    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for batchId '{batch_id}'")

    return products


@app.get("/health")
def health():
    return {"status": "ok"}