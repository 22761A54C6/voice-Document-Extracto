@echo off
REM Start the service on Windows (uses HOST/PORT from .env)
cd /d "%~dp0"
where uv >nul 2>nul || (
    echo uv is not installed. Install it with:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)
if not exist .env (
    echo .env not found - copy .env.example to .env and fill in MONGO_URI and GEMINI_API_KEY
    exit /b 1
)
uv sync
uv run python -m app.main
