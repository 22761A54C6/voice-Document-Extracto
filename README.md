# Voice AI Service

A FastAPI service that extracts product information from voice/audio input using speech recognition and LLM-powered text extraction.

## Overview

This service processes audio files to:
1. Transcribe speech to text using Whisper (faster-whisper)
2. Extract product names and prices using Google Gemini LLM
3. Normalize product names for search matching
4. Generate embeddings for category matching
5. Store products in MongoDB with category classifications

## Prerequisites

- Python 3.10 or higher Recommended - Python 3.11.10 
- MongoDB Atlas cluster (or local MongoDB)
- Google Gemini API key(present using free API Keys)
   use this link to get free API Keys: https://aistudio.google.com/app/apikey
   Gemini 3 Models 
   Gemini 3.6 Flash
   Gemini 3 Pro
   Gemini 3.5 Flash-Lite
   Gemini 2.5 Models
   Gemini 2.5 Pro
   Gemini 2.5 Flash
   Gemini 2.5 Flash-Lite
- OpenSearch (for logging)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd voice-ai-service
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

## Configuration

Edit `.env` file with your configuration:

### Required Variables

```env
# Service
SERVICE_NAME=voice-service
PORT=6001
HOST=localhost

# Gemini API (Required)
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-001
GEMINI_EMBED_DIMENSIONS=512

# MongoDB (Required)
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/bizlink
MONGO_DB_NAME=bizlink

# Whisper Model
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### Optional Variables (OpenSearch Logging)

```env
OPENSEARCH_ENABLED=true
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX_PREFIX=voice-logs
```

## Running the Service

### Development Mode

```bash
python -m app.main
```

The service will start on `http://localhost:6001`

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 6001 --workers 4
```

## API Endpoints

### POST /voice

Extract products from audio file.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: Audio file (mp3, wav, m4a, ogg, webm, aac)
- Max file size: 15MB

**Response:**
```json
{
  "batchId": "uuid-string",
  "products": [
    {
      "name": "Chicken Biryani",
      "price": 250.0,
      "batchId": "uuid-string"
    }
  ]
}
```

**Example using curl:**
```bash
curl -X POST http://localhost:6001/voice \
  -F "file=@audio.mp3"
```

### GET /products/voice/{batch_id}

Retrieve products by batch ID.

**Response:**
```json
[
  {
    "id": "product-id",
    "batchId": "batch-id",
    "name": "Chicken Biryani",
    "normalizedName": "chicken biryani",
    "price": 250.0,
    "matchedCategory": "Biryani",
    "matchedCategorySourceId": "category-source-id",
    "matchedCategoryScore": 0.98,
    "matchStatus": "AUTO_MAPPED"
  }
]
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## Architecture Flow

```
Audio File Upload
    ↓
Whisper Transcription (faster-whisper)
    ↓
Raw Text
    ↓
Gemini LLM Extraction (product name + price)
    ↓
Normalized Product Names (Gemini)
    ↓
Embeddings Generation (Gemini embedding model)
    ↓
Category Matching (MongoDB Vector Search)
    ↓
MongoDB Storage (with classification)
    ↓
Return Response with batchId
```

## Database Schema

### Products Collection
```json
{
  "_id": "uuid",
  "batchId": "uuid",
  "name": "Chicken Biryani",
  "normalizedName": "chicken biryani",
  "price": 250.0,
  "embedding": [0.1, 0.2, ...],
  "matchedCategory": "Biryani",
  "matchedCategorySourceId": "source-id",
  "matchedCategoryScore": 0.98,
  "matchStatus": "AUTO_MAPPED"
}
```

### Categories Collection
```json
{
  "_id": "category-id",
  "name": "Biryani",
  "sourceId": "source-id",
  "embedding": [0.1, 0.2, ...]
}
```

## Category Matching Logic

- **score > 0.95** → AUTO_MAPPED
- **0.85 ≤ score ≤ 0.95** → PENDING_VENDOR_CONFIRMATION
- **score < 0.85** → CREATE_NEW_CATEGORY_OR_ADMIN_APPROVAL

## Logging

Logs are sent to:
- Console (terminal output)
- OpenSearch (if enabled)

OpenSearch index pattern: `voice-logs-YYYY.MM.DD`

### OpenSearch Setup

#### 1. Download and Install OpenSearch

**Windows:**
```bash
# Download OpenSearch for Windows
# https://opensearch.org/downloads.html

# Extract to: C:\opensearch-3.7.0-windows-x64\opensearch-3.7.0
```

**Linux/Mac:**
```bash
# Download OpenSearch for Linux/Mac
# https://opensearch.org/downloads.html

# Extract and navigate
tar -xzf opensearch-3.7.0-linux-x64.tar.gz
cd opensearch-3.7.0
```

#### 2. Configure OpenSearch (Disable Security for Development)

Edit `config/opensearch.yml`:
```yaml
plugins.security.disabled: true
```

#### 3. Start OpenSearch

**Windows:**
```bash
cd C:\opensearch-3.7.0-windows-x64\opensearch-3.7.0\bin
.\opensearch.bat
```

**Linux/Mac:**
```bash
./opensearch-3.7.0/bin/opensearch
```

#### 4. Verify OpenSearch is Running

```bash
curl http://localhost:9200
```

Expected response:
```json
{
  "name": "opensearch-node",
  "cluster_name": "opensearch",
  "version": {
    "number": "3.7.0"
  }
}
```

#### 5. Configure OpenSearch Dashboards (Optional)

**Windows:**
```bash
cd C:\opensearch-dashboards-3.7.0-windows-x64\opensearch-dashboards-3.7.0\config
```

Edit `opensearch_dashboards.yml`:
```yaml
opensearch_security.enabled: false
```

**Start Dashboards:**
```bash
cd C:\opensearch-dashboards-3.7.0-windows-x64\opensearch-dashboards-3.7.0\bin
.\opensearch-dashboards.bat
```

Access Dashboards: http://localhost:5601

#### 6. Create Index Pattern in OpenSearch Dashboards

1. Open http://localhost:5601
2. Go to **Stack Management** → **Index Patterns**
3. Click **Create index pattern**
4. Enter pattern: `voice-logs-*`
5. Select `@timestamp` as time field
6. Click **Create index pattern**

#### 7. Verify Logs are Being Sent

```bash
# Check for voice-logs indices
curl http://localhost:9200/_cat/indices?v

# Search for logs
curl http://localhost:9200/voice-logs-*/_search
```

### OpenSearch Logging Working Process

```
Voice AI Service (FastAPI)
    ↓
Python Logging Module
    ↓
OpenSearchHandler (Background Thread)
    ↓
Queue (Log Records)
    ↓
HTTP POST to OpenSearch
    ↓
Index: voice-logs-YYYY.MM.DD
    ↓
OpenSearch Dashboards
    ↓
Visualize and Query Logs
```

### Log Document Structure

Each log entry in OpenSearch contains:
```json
{
  "@timestamp": "2026-07-24T08:00:00.000Z",
  "service": "voice-service",
  "level": "INFO",
  "logger": "app.main",
  "message": "Health check endpoint called",
  "path": "/path/to/file.py",
  "line": 177,
  "function": "health"
}
```

## Troubleshooting

### Whisper Model Loading Error
- First run downloads the model (~500MB for 'small' model)
- Ensure internet connection for initial download
- Model cached in `~/.cache/huggingface`

### Gemini API Errors
- Verify `GEMINI_API_KEY` is set correctly
- Check API quota and billing enabled
- Network connectivity to Google services

### MongoDB Connection Error
- Verify `MONGO_URI` is correct
- Check IP whitelist in MongoDB Atlas
- Ensure database user has proper permissions

### OpenSearch Connection Error
- Set `OPENSEARCH_ENABLED=false` if not using OpenSearch
- Verify OpenSearch is running on configured host/port
- Check network connectivity

### File Upload Errors
- Max file size: 15MB
- Supported formats: mp3, wav, m4a, ogg, webm, aac
- Ensure audio contains speech

## Dependencies

- fastapi==0.115.0
- uvicorn[standard]==0.30.6
- faster-whisper>=1.0.0
- requests==2.32.3
- pydantic==2.13.4
- python-multipart==0.0.9
- pymongo==4.9.2
- python-dotenv==1.0.1
- google-genai
- aiohttp

## Project Structure

```
voice-ai-service/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration and environment variables
│   ├── main.py                # FastAPI application and endpoints
│   ├── voice_service.py       # Whisper transcription
│   ├── extraction.py          # LLM product extraction
│   ├── normalization.py       # Product name normalization
│   ├── embeddings.py          # Embedding generation and storage
│   ├── matching.py            # Category matching logic
│   ├── database.py            # MongoDB connection
│   ├── models.py              # Pydantic models
│   └── logging_config.py      # OpenSearch logging setup
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## License

[Prospect InfoSystem Inc]


## Support

For issues and questions, please contact
 [Phone no: +91 96527 96086, +91 62813 70532].
 [EMAIL To: thalluridhanujay@gmail.com , tumati.bhanuprakash947@gmail.com ]



