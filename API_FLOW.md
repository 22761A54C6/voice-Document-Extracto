# API Flow – Voice AI Service

How a `POST /voice` request moves through the service, what the client receives, and what is stored in MongoDB.

## 1. `POST /voice`

Request: `multipart/form-data` with one field `file` (the audio).

```bash
curl -N -X POST http://localhost:8002/voice -F "file=@menu.m4a;type=audio/mp4"
```

### Step 0 – Validation (before streaming)

Runs in the endpoint (`app/api/extract_voice.py`) before any SSE event, so failures return a normal **HTTP 400**:

| Check | Error `detail` |
|---|---|
| content type in the allowed audio list (see README) | `Unsupported file type: <type>. Allowed: [...]` |
| file not empty | `Uploaded file is empty` |
| size ≤ `MAX_FILE_SIZE_MB` (5) | `File too large (max 5MB)` |

After validation the response is `text/event-stream` and processing runs in a background task. If the client disconnects, the task is cancelled.

### Step 1 – Transcription (`pipeline/transcription.py`)

- faster-whisper, model loaded once at startup (`WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_CPU_THREADS`).
- Audio is decoded **from memory** (no temp file), in a worker thread.
- Options: `beam_size=WHISPER_BEAM_SIZE` (1), `vad_filter=WHISPER_VAD_FILTER` (true), `language=WHISPER_LANGUAGE` (auto-detect when empty), no timestamps, `condition_on_previous_text=False`.
- Segment texts are joined with spaces.
- Empty transcript → error event `No speech detected in audio`. Decoding failure → `Audio transcription failed. Please try again.`

### Step 2 – Product extraction (`pipeline/product_extraction.py`)

1. Prompt rules: associate prices with products, keep sizes as variants (flat name/price/quantity only), no headings as products, numeric prices, short generated description when none is spoken, quantity / preparation time (minutes) only when mentioned, minified JSON.
2. Output budget: `len(transcript) × 1.2` tokens, clamped to 1000–8192.
3. Gemini call with `response_mime_type=application/json` and minimal thinking.
4. Up to **3 attempts** (1 s, 2 s back-off) on 429/500/503/UNAVAILABLE/RESOURCE_EXHAUSTED/overloaded.
5. Reply parsed as `{"products": [...]}` or a bare list; markdown fences are stripped.
6. Failure → error event `Product extraction failed. Please try again.`

LLM output shape:

```json
{"products":[{"product_name":"Filter Coffee","description":"…","price":null,"variants":[{"name":"Small","price":30},{"name":"Large","price":50}]}]}
```

### Step 3 – Normalize and fill defaults (`pipeline/product_normalizer.py`)

- Products without `product_name` are dropped; variants without a name or that aren't objects are dropped.
- Numbers are parsed leniently: `"$5.50"` → `5.5`, `"2 cups"` → `2`.
- Defaults:

| Field | Default |
|---|---|
| `description` | `""` |
| `price` | `0.0` |
| `quantity` | `0` |
| `preparationTime` | `0` |
| `variants` | `[]` |
| variant `vendorPrice` | the product's price |
| variant `availableQuantity` | `0` |

Nothing left → error event `No products could be extracted from this audio`.

### Step 4 – Embeddings, matching, storage (`pipeline/product_storage.py`, `pipeline/category_matching.py`)

1. All product names embedded in **one** Gemini call (`gemini-embedding-001`, `SEMANTIC_SIMILARITY`, 768 dims; batches of 100).
2. For each product, concurrently, Atlas `$vectorSearch` on `categories`: index `category_vector_index`, path `embedding`, `numCandidates` `VECTOR_SEARCH_NUM_CANDIDATES` (768), `limit` 1 (fixed values are in `app/core/constants.py`).
3. The closest category is used: `matchedCategory`, `matchedCategorySourceId` (returned as `categoryId`) and its similarity `matchedCategoryScore` (stored in MongoDB). No match → all three are `null`.
4. A failed lookup keeps the product with `null` category fields.
5. One batch document is inserted into `products` (§4).
6. Embedding or storage failure → error event `Failed to store products. Please try again.`

### Step 5 – Result

A `complete` progress event, then the result object as the final `data:` line:

```json
{
  "batchId": "uuid",
  "sourceType": "audio",
  "targetFormat": [ /* see §3 */ ],
  "processingTime": 3.96,
  "tokenUsage": {"prompt_tokens": 389, "completion_tokens": 158, "total_tokens": 547},
  "timingBreakdown": {
    "fileRead_ms": 0.1,
    "transcription_ms": 1276.5,
    "llmExtraction_ms": 1477.2,
    "embeddingAndStorage_ms": 1203.4,
    "total_ms": 3957.0
  }
}
```

`processingTime` is in seconds; `timingBreakdown` values are in milliseconds.

## 2. SSE events

Progress events have the shape `{"stage", "progress", "message", "timestamp"}`:

| stage | progress | message |
|---|---|---|
| `validation` | 5 | Validating file type and size |
| `upload` | 10 | Reading uploaded file |
| `preprocessing` | 15 | Preparing audio |
| `transcription` | 20 | Starting audio transcription |
| `transcription` | 50 | Audio transcription completed |
| `extraction` | 55 | Starting LLM product extraction |
| `extraction` | 75 | LLM product extraction completed |
| `embedding` | 80 | Generating embeddings and storing in database |
| `embedding` | 90 | Embeddings generated and stored |
| `complete` | 100 | Processing completed successfully |
| `error` | 0 | the error message (stream ends) |

After `complete`, one more event carries the result object (recognisable by `batchId`) and the stream ends. During long steps a `: keepalive` comment is sent every 30 s.

```
data: {"stage":"transcription","progress":50.0,"message":"Audio transcription completed","timestamp":1792215486.2}

data: {"stage":"complete","progress":100.0,"message":"Processing completed successfully","timestamp":1792215489.4}

data: {"batchId":"fe8378dd-…","sourceType":"audio","targetFormat":[…],…}
```

## 3. `targetFormat` product (API response)

Every field is always present.

```json
{
  "name": "Paneer Butter Masala",
  "description": "Rich and creamy paneer butter masala.",
  "categoryId": "e09663d2-2a16-4fcc-ba56-cc7b0c17f869",
  "quantity": 0,
  "preparationTime": 15,
  "price": 240.0,
  "variants": [{"name": "Half", "vendorPrice": 150.0, "availableQuantity": 0}]
}
```

| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `description` | string | spoken, generated by the LLM, or `""` |
| `categoryId` | string \| null | catalog category id of the best match |
| `quantity` | integer | |
| `preparationTime` | integer | minutes |
| `price` | number | `0.0` for products priced only by variants |
| `variants[].name` / `vendorPrice` / `availableQuantity` | string / number / integer | |

## 4. MongoDB data

Database: `MONGO_DB_NAME` (`bizlink_ollama`), shared with the Image-Text-Pdf service.

### `products` – one document per request

```json
{
  "_id": "ObjectId",
  "batchId": "uuid",
  "sourceType": "audio",
  "products": [
    {
      "id": "uuid",
      "batchId": "uuid",
      "name": "Masala Dosa",
      "description": "Delicious and traditional South Indian masala dosa.",
      "price": 120.0,
      "quantity": 0,
      "preparationTime": 0,
      "variants": [],
      "matchedCategory": "Tiffins & Breakfast",
      "matchedCategorySourceId": "76b22070-…",
      "matchedCategoryScore": 0.92,
      "embedding": [768 floats]
    }
  ],
  "targetFormat": [ /* same objects as the API response */ ],
  "processingTime": 3.2
}
```

### `categories` (read-only here)

Written by the Image-Text-Pdf service's category sync: `{sourceId, name, embeddedText, embedding[768], embeddingModel}`, searched through `category_vector_index` (`embedding`, 768 dims, cosine). Product embeddings use the same `GEMINI_EMBED_MODEL`, so scores are comparable.

## 5. `GET /health`

Runs three checks, each with a 5-second limit:

| Check | How |
|---|---|
| `mongodb` | `ping` command |
| `gemini` | fetch `GEMINI_MODEL` metadata (validates the API key) |
| `whisper_model` | model object loaded |

`status` is `ok` when all pass, otherwise `degraded`.

## 6. Error reference

| Message | Where |
|---|---|
| `Unsupported file type: …` / `Uploaded file is empty` / `File too large (max 5MB)` | HTTP 400 |
| `No speech detected in audio` | error event |
| `Audio transcription failed. Please try again.` | error event |
| `Product extraction failed. Please try again.` | error event |
| `No products could be extracted from this audio` | error event |
| `Failed to store products. Please try again.` | error event |
| `Processing failed. Please try again.` | error event (unexpected error) |
| `An unexpected error occurred. Please try again.` | HTTP 500 |

## 7. Tracing

`X-Trace-Id` request header → used as the trace id (otherwise a new one is generated) and returned in the `X-Trace-Id` response header. A span id is also generated for each request and returned in the `X-Span-Id` response header. The background task and worker threads (transcription, vector search, storage) inherit both ids, so all log lines of one request share the same trace id and span id. At INFO a request logs two lines: the request and the result summary (see RUNNING.md → Logs).
