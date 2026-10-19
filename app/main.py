import sys

# Windows consoles default to a legacy code page (e.g. cp1252); without this,
# logging product names with ₹, Hindi text or emoji fails with encoding errors.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

if __name__ == "__main__":
    # Start the server without importing the app here: uvicorn imports app.main
    # itself, so importing it in this launcher process would load Whisper twice.
    import uvicorn
    from app.core.config import HOST, PORT, RELOAD
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=RELOAD)
    raise SystemExit

from app.core.config import validate_required_env_vars  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402

# Must run before importing the routers: they load the Whisper model and
# connect to MongoDB at import time.
configure_logging()
validate_required_env_vars()

from app.core.app import create_app  # noqa: E402
from app.api import extract_voice, health, test_ui  # noqa: E402

app = create_app()

# Include routers
app.include_router(extract_voice.router)
app.include_router(health.router)
app.include_router(test_ui.router)
