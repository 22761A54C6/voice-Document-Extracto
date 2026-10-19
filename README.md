# Voice AI Service

FastAPI service that turns a **spoken product/menu description** into a structured product catalog: **faster-whisper** transcribes the audio locally, **Google Gemini** extracts the products, and **MongoDB Atlas Vector Search** maps each product to a catalog category.

Repository: https://github.com/22761A54C6/Voice-Ai-Service

Sister service: [Image-Text-Pdf AI Service](https://github.com/22761A54C6/image-text-pdf-ai-service) – same pipeline for images/PDFs/text. Both services write to the same MongoDB collections, and the Image-Text-Pdf service maintains the shared category vectors.

## Features

- **Speech-to-text** – faster-whisper (`small`, CPU, int8) with voice-activity filtering and automatic language detection; audio is processed in memory.
- **Product parsing** – Gemini returns name, description, price, quantity, preparation time and size variants as JSON.
- **Complete output** – every product always has every field; defaults are used when the LLM leaves something out.
- **Category matching** – product names embedded with `gemini-embedding-001` (768 dims) and matched with Atlas Vector Search.
- **Live progress** – `POST /voice` streams Server-Sent Events; processing stops if the client disconnects.
- **Health checks** – `/health` checks MongoDB, Gemini and the Whisper model.
- **Production logging** – two lines per request at INFO (request + result summary), every step at DEBUG, optional JSON output (`LOG_FORMAT=json`); a full trace id and span id on every line, taken from / returned in `X-Trace-Id`.
- **Test UI** – `GET /voice-products-extract-using-ai` (record or upload audio).

## How it works

```
POST /voice (audio file)
   │ validate type/size  ──► HTTP 400 on failure
   ▼
faster-whisper transcription (worker thread)
   ▼
Gemini product extraction (JSON) ─► normalize + default values
   ▼
Gemini embeddings (product names, one batch call)
   ▼
Atlas $vectorSearch on categories (category_vector_index)
   ▼
store batch in products collection ─► SSE result event
```

Step-by-step details and schemas: [API_FLOW.md](API_FLOW.md). Setup and operations: [RUNNING.md](RUNNING.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/voice` | Extract products from an audio file (multipart `file`, max 5 MB) – SSE |
| GET | `/health` | Checks MongoDB, Gemini and the Whisper model |
| GET | `/voice-products-extract-using-ai` | Browser test UI |

Supported audio types: `audio/mpeg`, `audio/mp3`, `audio/wav`, `audio/x-wav`, `audio/m4a`, `audio/x-m4a`, `audio/mp4`, `audio/aac`, `audio/ogg`, `audio/webm`, `audio/opus`, `audio/flac`, `audio/x-flac`, `audio/aiff`, `audio/x-aiff`, `audio/wma`, `audio/x-ms-wma`, `audio/amr`, `audio/x-amr`, `audio/3gpp`, `audio/3gpp2`.

## Response format (final SSE event)

```json
{
  "batchId": "fe8378dd-…",
  "sourceType": "audio",
  "targetFormat": [
    {
      "name": "Filter Coffee",
      "description": "Authentic South Indian filter coffee.",
      "categoryId": "d376c33b-…",
      "quantity": 0,
      "preparationTime": 0,
      "price": 0.0,
      "variants": [
        {"name": "Small", "vendorPrice": 30.0, "availableQuantity": 0},
        {"name": "Large", "vendorPrice": 50.0, "availableQuantity": 0}
      ]
    }
  ],
  "processingTime": 3.96,
  "tokenUsage": {"prompt_tokens": 389, "completion_tokens": 158, "total_tokens": 547},
  "timingBreakdown": {"fileRead_ms": 0.1, "transcription_ms": 1276, "llmExtraction_ms": 1477, "embeddingAndStorage_ms": 1203, "total_ms": 3957}
}
```

Default values when the LLM does not provide a field:

| Field | Default |
|---|---|
| `description` | `""` |
| `price` | `0.0` |
| `quantity` | `0` |
| `preparationTime` | `0` (minutes) |
| `variants` | `[]` |
| variant `vendorPrice` | the product's `price` |
| variant `availableQuantity` | `0` |
| `categoryId` | `null` when no category matched |

## Configuration

Copy `.env.example` to `.env`. Required: `MONGO_URI`, `GEMINI_API_KEY`.

| Variable | Default | Notes |
|---|---|---|
| `PORT` / `HOST` / `RELOAD` | `8002` / `0.0.0.0` / `false` | |
| `MONGO_URI` / `MONGO_DB_NAME` | – / `bizlink_ollama` | **Required.** Same database as Image-Text-Pdf |
| `GEMINI_API_KEY` | – | **Required** |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Product extraction |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Must match the model used for category vectors |
| `GEMINI_THINKING_LEVEL` | `minimal` | For `gemini-3.8-flash` set `GEMINI_THINKING_BUDGET=0` instead |
| `GEMINI_TEMPERATURE` / `GEMINI_TIMEOUT_MS` | `0` / `120000` | |
| `MAX_FILE_SIZE_MB` | `5` | |
| `WHISPER_MODEL_SIZE` | `small` | `base` is ~2× faster, less accurate |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `cpu` / `int8` | |
| `WHISPER_BEAM_SIZE` | `1` | |
| `WHISPER_VAD_FILTER` | `true` | Skip silence |
| `WHISPER_CPU_THREADS` | all cores | |
| `WHISPER_LANGUAGE` | auto-detect | Set e.g. `en` to skip detection |
| `VECTOR_SEARCH_NUM_CANDIDATES` | `768` | |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | `DEBUG` for every step; `json` for log aggregators |
| `FASTER_WHISPER_LOG_LEVEL` | `WARNING` | |

## Settings, constants and messages

No values are hard-coded in the code. They live in three places under `app/core/`:

| File | Holds | Change it by |
|---|---|---|
| `config.py` | Settings that differ between environments: keys, MongoDB, models, timeouts, upload limit, Whisper options | Editing `.env` (table above) |
| `constants.py` | Fixed values the code depends on: routes, collection and index names (`products`, `categories`, `category_vector_index`), embedding size (768), SSE stages and progress percentages, keepalive interval, retry count, LLM token budget, product defaults, log format | Editing the file (a code change) |
| `messages.py` | Every message returned to clients (HTTP error details, SSE progress and error messages, health check messages) | Editing the file |

The Gemini prompt is in `app/pipeline/prompts.py`. HTTP status codes use FastAPI's named constants (`status.HTTP_400_BAD_REQUEST`, ...).

## Project structure

Same layout as the Image-Text-Pdf service: `api/` receives the request, `pipeline/` does the work step by step, `clients/` talks to outside services.

```
app/
├── main.py                      # App startup: logging, env check, routers
├── core/                        # Shared setup
│   ├── app.py                   # FastAPI factory, request log, global error handler
│   ├── config.py                # Environment settings (.env)
│   ├── constants.py             # Fixed values: routes, collections, stages, limits, defaults
│   ├── messages.py              # Messages returned to clients
│   ├── database.py              # MongoDB connection
│   └── logging.py               # Log format (text/json), trace id
├── api/                         # HTTP endpoints
│   ├── extract_voice.py         # POST /voice – upload checks, SSE progress, runs the pipeline
│   ├── health.py                # GET /health
│   ├── test_ui.py               # GET /voice-products-extract-using-ai
│   └── schemas.py               # SSE progress event
├── pipeline/                    # Processing steps, in order
│   ├── transcription.py         # 1. Audio → text (faster-whisper)
│   ├── prompts.py               # Gemini extraction prompt
│   ├── product_extraction.py    # 2. Text → products (Gemini call, retries, JSON parsing)
│   ├── product_normalizer.py    # 3. Fill defaults, build target format
│   ├── category_matching.py     # 4. Atlas $vectorSearch for the closest category
│   └── product_storage.py       # 4. Embed product names, match categories, store the batch
└── clients/
    └── gemini.py                # Gemini client: embeddings, health check
static/test_ui.html              # Browser test UI
scripts/smoke_test.py            # End-to-end check of /voice
```

## Dependencies

FastAPI, Uvicorn, faster-whisper, `google-genai`, PyMongo, python-dotenv, python-multipart (see `pyproject.toml`; managed with `uv`).
