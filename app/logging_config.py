"""
Centralized logging setup for OpenSearch.

Configures the root logger to send logs synchronously to OpenSearch
using requests for HTTP requests.

Logs are indexed with daily pattern: voice-logs-YYYY.MM.DD

Call configure_logging() once, as early as possible in main.py --
before any other module-level code that might log.
"""
import logging
import os
from datetime import datetime
from threading import Thread
import queue

import requests

SERVICE_NAME = os.environ.get("SERVICE_NAME", "voice-service")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# OpenSearch configuration
OPENSEARCH_ENABLED = os.environ.get("OPENSEARCH_ENABLED", "false").lower() == "true"
OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", 9200))
OPENSEARCH_INDEX_PREFIX = os.environ.get("OPENSEARCH_INDEX_PREFIX", "voice-logs")

_configured = False


class OpenSearchHandler(logging.Handler):
    """Handler that sends logs to OpenSearch via HTTP in background thread."""
    
    def __init__(self, host: str, port: int, index_prefix: str):
        super().__init__()
        self.host = host
        self.port = port
        self.index_prefix = index_prefix
        self.queue = queue.Queue(maxsize=1000)
        self._worker_thread = None
        self._running = False
        
    def emit(self, record: logging.LogRecord) -> None:
        """Queue log record for background processing."""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass  # Drop logs if queue is full
            
    def _send_log(self, record: logging.LogRecord) -> None:
        """Send log record to OpenSearch."""
        # Create index name with date: voice-logs-2026.07.24
        index_name = f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"
        
        # Build log document
        log_doc = {
            "@timestamp": datetime.utcnow().isoformat() + "Z",
            "service": SERVICE_NAME,
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
            "path": getattr(record, 'pathname', ''),
            "line": getattr(record, 'lineno', 0),
            "function": getattr(record, 'funcName', ''),
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_doc.update(record.extra_fields)
            
        url = f"http://{self.host}:{self.port}/{index_name}/_doc"
        
        try:
            response = requests.post(url, json=log_doc, timeout=5)
            if response.status_code not in (200, 201):
                pass  # Silently fail on errors
        except Exception:
            pass  # Silently fail on network errors
            
    def _worker(self) -> None:
        """Background worker to process queued logs."""
        while self._running:
            try:
                record = self.queue.get(timeout=1)
                self._send_log(record)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                continue
                
    def start(self) -> None:
        """Start the background worker thread."""
        if self._worker_thread is None:
            self._running = True
            self._worker_thread = Thread(target=self._worker, daemon=True)
            self._worker_thread.start()
            
    def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)
            
    def close(self) -> None:
        """Close handler."""
        self.stop()
        super().close()


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    handlers = []
    
    # Console handler for local debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    handlers.append(console_handler)
    
    # OpenSearch handler if enabled
    if OPENSEARCH_ENABLED:
        opensearch_handler = OpenSearchHandler(
            host=OPENSEARCH_HOST,
            port=OPENSEARCH_PORT,
            index_prefix=OPENSEARCH_INDEX_PREFIX
        )
        opensearch_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(opensearch_handler)
        
        # Start the background worker
        opensearch_handler.start()
        
        # Store handler reference for shutdown
        logging.getLogger().opensearch_handler = opensearch_handler

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.handlers = handlers

    _configured = True
