"""Logging setup: one line per event, trace id and span id on every line.

LOG_FORMAT=text (default) -- human-readable, full trace id and span id:
    2026-10-17 12:06:11 INFO    [trace=7a75ef4ca123b456c789d012e345f678] [span=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6] voice: 3 products in 3.96s | audio=11.8s lang=en ...
LOG_FORMAT=json -- one JSON object per line for log aggregators (full trace id and span id).
LOG_LEVEL=DEBUG shows every pipeline step; INFO shows one summary line per request.
"""
import json
import logging
import os
import sys
import traceback
import uuid
from contextvars import ContextVar
from typing import Optional

from app.core.config import LOG_LEVEL, LOG_FORMAT, FASTER_WHISPER_LOG_LEVEL
from app.core.constants import (
    SERVICE_NAME, LOG_LINE_FORMAT, LOG_DATE_FORMAT, LOG_JSON_DATE_FORMAT, LOG_FORMAT_JSON,
    NOISY_LOGGERS, LOG_LEVEL_DEBUG, FASTER_WHISPER_LOGGER,
)

trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_ctx: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


# Our own code; library frames are left out of stack traces unless LOG_LEVEL=DEBUG
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _keep_app_frames(tb_exc: traceback.TracebackException) -> None:
    """Drop framework/library frames, keeping our code and the frame that raised."""
    frames = list(tb_exc.stack)
    kept = [f for f in frames if f.filename.startswith(APP_DIR)]
    if frames and frames[-1] not in kept:
        kept.append(frames[-1])
    tb_exc.stack = traceback.StackSummary.from_list(kept)
    # Implicit context raised entirely inside a library (e.g. anyio's EndOfStream) is noise
    context = tb_exc.__context__
    if context is not None and not any(f.filename.startswith(APP_DIR) for f in context.stack):
        tb_exc.__context__ = None
    for chained in (tb_exc.__cause__, tb_exc.__context__):
        if chained is not None:
            _keep_app_frames(chained)


def format_exception(exc_info) -> str:
    tb_exc = traceback.TracebackException(*exc_info)
    if LOG_LEVEL != LOG_LEVEL_DEBUG:
        _keep_app_frames(tb_exc)
    return "".join(tb_exc.format()).rstrip()


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """Use the caller's trace id (X-Trace-Id) or start a new one for this request.
    Also generates a new span_id for this request."""
    trace_id = trace_id or uuid.uuid4().hex
    trace_id_ctx.set(trace_id)
    span_id = uuid.uuid4().hex
    span_id_ctx.set(span_id)
    return trace_id


def get_span_id() -> Optional[str]:
    """Get the current span id."""
    return span_id_ctx.get()


def root_cause(exc: BaseException) -> BaseException:
    """Deepest exception in the `raise ... from` chain -- the actual reason for a failure."""
    while exc.__cause__ is not None:
        exc = exc.__cause__
    return exc


class TextFormatter(logging.Formatter):
    def formatException(self, ei):
        return format_exception(ei)

    def format(self, record):
        trace_id = trace_id_ctx.get()
        span_id = span_id_ctx.get()
        if trace_id:
            record.trace = f"[trace={trace_id}] "
        else:
            record.trace = ""
        if span_id:
            record.span = f"[span={span_id}] "
        else:
            record.span = ""
        return super().format(record)


class JsonFormatter(logging.Formatter):
    def formatException(self, ei):
        return format_exception(ei)

    def format(self, record):
        entry = {
            "time": self.formatTime(record, LOG_JSON_DATE_FORMAT),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "trace_id": trace_id_ctx.get(),
            "span_id": span_id_ctx.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if LOG_FORMAT == LOG_FORMAT_JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter(LOG_LINE_FORMAT, LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(LOG_LEVEL)

    # Uvicorn's startup/error lines use the same format; its access log is replaced
    # by the request log in app.core.app
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    logging.getLogger(FASTER_WHISPER_LOGGER).setLevel(FASTER_WHISPER_LOG_LEVEL)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
