@echo off
setlocal
cd /d "%~dp0"

echo Updating dependencies (incl. youtube-transcript-api)...
python -m pip install --upgrade -r requirements.txt || echo Update failed - starting with installed versions.

echo.
echo Serving at http://127.0.0.1:8000  (press Ctrl+C to stop)
python -m uvicorn server:app --host 127.0.0.1 --port 8000
