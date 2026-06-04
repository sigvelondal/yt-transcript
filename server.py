from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from youtube_transcript_api import YouTubeTranscriptApi

BASE_DIR = Path(__file__).parent
app = FastAPI()
_api = YouTubeTranscriptApi()


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
        return {
            "video_id": v,
            "language": result.language_code,
            "language_name": result.language,
            "is_generated": result.is_generated,
            "text": text,
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
