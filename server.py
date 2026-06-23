import os
import tempfile
import http.cookiejar
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from youtube_transcript_api import YouTubeTranscriptApi

BASE_DIR = Path(__file__).parent
app = FastAPI()


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    cookies_content = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if cookies_content:
        jar = http.cookiejar.MozillaCookieJar()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(cookies_content)
            tmp = f.name
        try:
            jar.load(tmp, ignore_discard=True, ignore_expires=True)
            session.cookies = requests.utils.cookiejar_from_dict(
                {c.name: c.value for c in jar}
            )
        finally:
            os.unlink(tmp)
    return session


_api = YouTubeTranscriptApi(http_client=_make_session())


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/transcript")
async def get_transcript(
    v: str = Query(..., min_length=1, max_length=20),
    lang: str = Query(default="en", max_length=10),
):
    try:
        try:
            result = _api.fetch(v, languages=[lang, "en"])
        except Exception:
            tl = _api.list(v)
            t = next(iter(tl))
            result = t.fetch()

        text = " ".join(s.text.replace("\n", " ") for s in result.snippets)
        segments = [
            {"start": float(s.start), "text": s.text.replace("\n", " ").strip()}
            for s in result.snippets
        ]
        return {
            "video_id": v,
            "language": result.language_code,
            "language_name": result.language,
            "is_generated": result.is_generated,
            "text": text,
            "segments": segments,
            "word_count": len(text.split()),
        }
    except Exception as e:
        msg = str(e)
        if "disabled" in msg.lower():
            detail = "Transcripts are disabled for this video."
        elif "no transcript" in msg.lower() or "could not retrieve" in msg.lower():
            detail = "No transcript available for this video."
        else:
            detail = f"Could not fetch transcript: {msg}"
        raise HTTPException(status_code=400, detail=detail)
