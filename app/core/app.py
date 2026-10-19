import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import APP_TITLE, MILLISECONDS_PER_SECOND, QUIET_PATHS, ROUTE_FAVICON, TRACE_ID_HEADER, SPAN_ID_HEADER
from app.core.logging import set_trace_id, get_span_id
from app.core.messages import UNEXPECTED_ERROR

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """One log line per request; the trace id and span id are returned in headers.
        For /voice this logs when streaming starts -- the pipeline logs its own result."""
        trace_id = set_trace_id(request.headers.get(TRACE_ID_HEADER))
        span_id = get_span_id()
        start_time = time.time()

        def request_line(status_code: int) -> str:
            elapsed_ms = (time.time() - start_time) * MILLISECONDS_PER_SECOND
            return f"{request.method} {request.url.path} {status_code} {elapsed_ms:.0f}ms"

        try:
            response = await call_next(request)
        except Exception as exc:
            # Unexpected error: one ERROR line with the cause and stack trace, clean JSON for the client
            logger.error(f"{request_line(status.HTTP_500_INTERNAL_SERVER_ERROR)}: {type(exc).__name__}: {exc}", exc_info=exc)
            response = JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": UNEXPECTED_ERROR})
            response.headers[TRACE_ID_HEADER] = trace_id
            response.headers[SPAN_ID_HEADER] = span_id
            return response

        response.headers[TRACE_ID_HEADER] = trace_id
        response.headers[SPAN_ID_HEADER] = span_id
        if request.url.path not in QUIET_PATHS:
            if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                level = logging.ERROR
            elif response.status_code >= status.HTTP_400_BAD_REQUEST:
                level = logging.WARNING
            else:
                level = logging.INFO
            # Failed requests carry the reason set by the exception handlers below
            detail = getattr(request.state, "error_detail", None)
            reason = f": {detail}" if detail else ""
            logger.log(level, f"{request_line(response.status_code)}{reason}")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def remember_http_error(request: Request, exc: StarletteHTTPException):
        """Keep the error detail so the request log line says why the request failed."""
        request.state.error_detail = exc.detail
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def remember_validation_error(request: Request, exc: RequestValidationError):
        request.state.error_detail = "; ".join(
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in exc.errors()
        )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Fallback for errors raised outside the request middleware -- the client
        still gets clean JSON instead of a raw 500/traceback."""
        logger.error(f"Unhandled error on {request.method} {request.url.path}: {type(exc).__name__}: {exc}", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": UNEXPECTED_ERROR},
        )

    @app.get(ROUTE_FAVICON, include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
