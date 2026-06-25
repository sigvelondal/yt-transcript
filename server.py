import os
import tempfile
import http.cookiejar
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    VideoUnplayable,
    AgeRestricted,
    InvalidVideoId,
    RequestBlocked,
    PoTokenRequired,
    CouldNotRetrieveTranscript,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

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


def _make_proxy_config():
    """Optional proxy to get around YouTube's datacenter-IP block.

    YouTube blocks the transcript endpoint from most cloud IPs (Railway, AWS,
    etc.), which surfaces as RequestBlocked/IpBlocked. Set Webshare credentials
    or a generic proxy URL via env vars to route through a residential proxy.
    With none set, requests go out directly (fine when running locally).
    """
    ws_user = os.environ.get("WEBSHARE_PROXY_USERNAME", "").strip()
    ws_pass = os.environ.get("WEBSHARE_PROXY_PASSWORD", "").strip()
    if ws_user and ws_pass:
        return WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass)

    proxy_url = os.environ.get("PROXY_URL", "").strip()
    http_url = os.environ.get("PROXY_HTTP_URL", "").strip() or proxy_url
    https_url = os.environ.get("PROXY_HTTPS_URL", "").strip() or proxy_url
    if http_url or https_url:
        return GenericProxyConfig(http_url=http_url or None, https_url=https_url or None)

    return None


_api = YouTubeTranscriptApi(
    proxy_config=_make_proxy_config(),
    http_client=_make_session(),
)


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
        except NoTranscriptFound:
            # Requested languages aren't available; fall back to any transcript.
            result = next(iter(_api.list(v))).fetch()
    except RequestBlocked:
        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube is blocking this server's IP (common on cloud hosts like "
                "Railway). Set WEBSHARE_PROXY_USERNAME/WEBSHARE_PROXY_PASSWORD or "
                "PROXY_URL to route through a proxy, or run it locally."
            ),
        )
    except PoTokenRequired:
        raise HTTPException(
            status_code=503,
            detail="YouTube is requiring a PO token for this video right now. Try again later.",
        )
    except TranscriptsDisabled:
        raise HTTPException(status_code=400, detail="Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript available for this video.")
    except (VideoUnavailable, VideoUnplayable):
        raise HTTPException(status_code=404, detail="This video is unavailable.")
    except AgeRestricted:
        raise HTTPException(
            status_code=403,
            detail="This video is age-restricted, so its transcript can't be fetched without sign-in.",
        )
    except InvalidVideoId:
        raise HTTPException(status_code=400, detail="That doesn't look like a valid YouTube video ID.")
    except CouldNotRetrieveTranscript as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch transcript: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

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
