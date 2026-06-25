@echo off
setlocal
cd /d "%~dp0"

REM --- Optional proxy (only needed if YouTube blocks your IP; leave commented to run direct) ---
REM Generic proxy URL:
REM set PROXY_URL=http://user:pass@host:port
REM Or Webshare credentials:
REM set WEBSHARE_PROXY_USERNAME=your-username
REM set WEBSHARE_PROXY_PASSWORD=your-password

echo Updating dependencies (incl. youtube-transcript-api)...
python -m pip install --upgrade -r requirements.txt || echo Update failed - starting with installed versions.

echo.
echo Serving at http://127.0.0.1:8000  (press Ctrl+C to stop)
python -m uvicorn server:app --host 127.0.0.1 --port 8000
