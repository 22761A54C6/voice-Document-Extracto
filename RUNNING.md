# Running the Voice AI Service

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** – `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Google Gemini API key** – from https://aistudio.google.com/apikey
- **MongoDB Atlas** – the same cluster/database as the Image-Text-Pdf service
- **Category vectors** – the `categories` collection and `category_vector_index` are created by the Image-Text-Pdf service's category sync. Without them every product gets `categoryId: null`.
- ~1 GB disk for the Whisper model cache. No system ffmpeg is needed (faster-whisper bundles its decoder).

## Install

```bash
git clone https://github.com/22761A54C6/Voice-Ai-Service.git
cd Voice-Ai-Service
uv sync
```

## Configure

```bash
cp .env.example .env
```

Set at least:

```env
MONGO_URI=mongodb+srv://user:password@cluster0.xxxx.mongodb.net/?appName=Cluster0
MONGO_DB_NAME=bizlink_ollama
GEMINI_API_KEY=your-gemini-api-key
```

All other settings are optional – see the table in [README.md](README.md#configuration).

## Run

```bash
# Uses HOST / PORT / RELOAD from .env (default 0.0.0.0:8002)
uv run python -m app.main

# Or directly
uv run uvicorn app.main:app --host 0.0.0.0 --port 8002

# Development with auto-reload
uv run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

Port 8002 must be free – check with `lsof -iTCP:8002 -sTCP:LISTEN`.

### What happens at startup

1. Logging is configured and `MONGO_URI` is checked; the process exits with an error if it is missing.
2. The Whisper model loads. **The first run downloads it** (~460 MB for `small`) to `~/.cache/huggingface`.
3. Routers are registered and the server starts.

Use one worker per process: each worker loads its own Whisper model into memory.

## Verify

```bash
curl http://localhost:8002/health
```

```json
{"status":"ok","checks":{
  "mongodb":{"status":"ok","message":"MongoDB connection successful"},
  "gemini":{"status":"ok","message":"Gemini API reachable"},
  "whisper_model":{"status":"ok","message":"Whisper model loaded"}}}
```

`status` is `degraded` if any check fails.

Open the test UI: http://localhost:8002/voice-products-extract-using-ai

### Try the endpoint

```bash
curl -N -X POST http://localhost:8002/voice -F "file=@menu.m4a;type=audio/mp4"
```

`-N` shows the SSE progress events as they arrive. The last `data:` line (the one with `batchId`) is the result.

## Typical timings

For a ~10-second clip on an Apple Silicon laptop with `gemini-3.5-flash-lite`:

| Step | Time |
|---|---|
| Transcription | ~1.2–1.3 s |
| LLM extraction | ~1.4–1.5 s |
| Embeddings + matching + storage | ~0.7–1.2 s |
| **Total** | **~3.3–4 s** |

Faster options: `WHISPER_LANGUAGE=en` (skip language detection), `WHISPER_MODEL_SIZE=base` (~2× faster transcription, lower accuracy).

## Running on Windows

Everything runs natively on Windows 10/11 (x64) – no WSL, Docker or ffmpeg install needed.

1. **Install uv** (PowerShell):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Open a new terminal afterwards. uv downloads Python 3.11 automatically (pinned in `.python-version`).
2. **Install the Microsoft Visual C++ Redistributable (x64)** if it isn't already present – faster-whisper's native libraries (CTranslate2, ONNX Runtime) need it: https://aka.ms/vs/17/release/vc_redist.x64.exe
3. **Get the code and configure**:
   ```powershell
   git clone https://github.com/22761A54C6/Voice-Ai-Service.git
   cd Voice-Ai-Service
   Copy-Item .env.example .env
   notepad .env      # set MONGO_URI and GEMINI_API_KEY
   ```
4. **Start** – double-click `start.bat`, or:
   ```powershell
   .\start.bat
   ```
   It runs `uv sync` and then `uv run python -m app.main` (HOST/PORT/RELOAD from `.env`, default port 8002). Allow access if Windows Firewall asks. The first start downloads the Whisper model to `%USERPROFILE%\.cache\huggingface`; a warning about symlinks is harmless (enable Windows Developer Mode to silence it).
5. **Test** – in PowerShell use `curl.exe` (plain `curl` is an alias for `Invoke-WebRequest`):
   ```powershell
   curl.exe http://localhost:8002/health
   curl.exe -N -X POST http://localhost:8002/voice -F "file=@menu.m4a;type=audio/mp4"
   ```

6. **Check voice end to end** – with the service running, in a second terminal:
   ```powershell
   uv run python scripts/smoke_test.py
   ```
   It speaks a sample menu into a WAV file with Windows' built-in text-to-speech, sends it to `/voice` and prints `PASS`/`FAIL` (exit code 0 when all pass). To test your own recording: `uv run python scripts/smoke_test.py C:\path\to\menu.m4a`.

Windows equivalents of the commands in this guide:

| Task | Windows (PowerShell) |
|---|---|
| Who is using port 8002 | `netstat -ano \| findstr :8002` then `taskkill /PID <pid> /F` |
| Stop the service | `Ctrl+C` in its window |

Log output is forced to UTF-8, so transcripts and product names in any language log correctly in any console.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ERROR: Missing required environment variables: MONGO_URI` | Add `MONGO_URI` to `.env` |
| `address already in use` on 8002 | Another process holds the port – stop it or change `PORT` |
| Health `gemini: GEMINI_API_KEY is not set` | Add `GEMINI_API_KEY` and restart |
| `404 NOT_FOUND … model … no longer available` | Set `GEMINI_MODEL` to a model your key can use |
| `400 … Thinking level MINIMAL is not supported` | Use `GEMINI_THINKING_BUDGET=0` for that model |
| HTTP 400 `Unsupported file type` | Send a supported audio content type (see README); Safari/iOS recordings are `audio/mp4` |
| `No speech detected in audio` | Silent or very quiet recording (voice-activity filter removed everything) |
| `Audio transcription failed` | Corrupt or undecodable audio file |
| Every product has `categoryId: null` | `categories` / `category_vector_index` missing – run the Image-Text-Pdf category sync |
| Products get unrelated categories | Category vectors were made by another model – run `POST /sync/categories` on the Image-Text-Pdf service |
| Slow first request | Whisper model download on first start; later starts load from cache |
| Windows: `ImportError: DLL load failed` (ctranslate2 / onnxruntime) | Install the Visual C++ Redistributable x64 (see "Running on Windows") |

## Logs

At the default `LOG_LEVEL=INFO` each request writes **two lines** – the request and its result – and every line carries the full trace id, span id, and batch id:

```
2026-10-17 12:11:21 INFO    [trace=310f6fbc...] [span=a1b2c3d4...] POST /voice 200 2ms
2026-10-17 12:11:25 INFO    [trace=310f6fbc...] [span=a1b2c3d4...] voice: 3 products in 3.84s | audio=11.8s lang=en transcription=1.31s llm=1.18s embedding+db=1.35s tokens=487 batch=7416f3f2-a1b2-c3d4-e5f6-a1b2c3d4e5f6
2026-10-17 12:11:25 WARNING [trace=30f56c3a...] [span=e5f6g7h8...] voice: failed at transcription after 0.00s: Audio transcription failed. Please try again. (InvalidDataError: …)
2026-10-17 12:50:41 ERROR   [trace=63cdf519...] [span=i9j0k1l2...] voice: failed at extraction after 1.41s: Product extraction failed. Please try again. (ClientError: 400 INVALID_ARGUMENT … API key not valid …)
```

Rejected requests say why on the request line, and unexpected crashes log one ERROR line with the cause followed by a short stack trace of the service's own code (set `LOG_LEVEL=DEBUG` to include library frames):

```
2026-10-17 12:50:39 WARNING [ce28644c] POST /voice 400 1ms: Uploaded file is empty
2026-10-17 12:49:55 ERROR   [18d82a74] GET /some/path 500 1ms: KeyError: 'price'
Traceback (most recent call last):
  File ".../app/...py", line 42, in load_price
    return menu["price"]
KeyError: 'price'
```

Rule of thumb: **WARNING = the request or input was bad** (client must fix it), **ERROR = the service or a dependency failed** (someone on the team must look at it).

| Level | What is logged |
|---|---|
| INFO | startup (Whisper model load time), one line per request, one result line per extraction |
| WARNING | 4xx responses with the reason, extractions that failed because of the input (no speech, undecodable audio, no products), Gemini retries, products saved without a category, client disconnects |
| ERROR | 5xx responses with the reason, extractions that failed in Gemini / embeddings / MongoDB (with the root cause), failing health checks (MongoDB, Gemini), unexpected errors (with stack trace) |
| DEBUG | transcript, language detection, raw LLM output, per-product category matches, Gemini timings |

Settings:

| Variable | Values |
|---|---|
| `LOG_LEVEL` | `INFO` (default, production), `DEBUG` (troubleshooting), `WARNING` (problems only) |
| `LOG_FORMAT` | `text` (default) or `json` – one JSON object per line with `time`, `level`, `service`, `logger`, full `trace_id`, `message`, `exception`, for log aggregators (ELK, Loki, CloudWatch, Datadog) |
| `FASTER_WHISPER_LOG_LEVEL` | `WARNING` (default) |

Tracing: send `X-Trace-Id` with a request to use your own id (e.g. the gateway's); the id is returned in the `X-Trace-Id` response header. A span id is also generated and returned in the `X-Span-Id` response header. Both ids appear on every line of that request. `/health` and `/favicon.ico` are not logged. Third-party libraries (httpx, Gemini SDK, pymongo, Hugging Face) only log warnings. With `RELOAD=true` uvicorn's file watcher prints a few extra startup lines – use `RELOAD=false` in production.

## Security notes

- There is no authentication; run the service behind the API gateway.
- Keep `.env` out of version control (it is in `.gitignore`).
