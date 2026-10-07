import os
import tempfile

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.extractor import _quality_sort_key, download_video, get_video_info

app = FastAPI(title="Universal Video Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _select_format(formats, preferred_quality: str | None = None):
    if not formats:
        return None

    if preferred_quality:
        preferred = preferred_quality.lower()
        matches = [f for f in formats if preferred in str(f.get("quality", "")).lower()]
        if matches:
            return max(matches, key=lambda item: _quality_sort_key(item.get("quality")))

    return max(formats, key=lambda item: _quality_sort_key(item.get("quality")))


def _build_mobile_payload(info, selected):
    formats = []
    for item in info.get("formats", []):
        formats.append({
            "quality": item.get("quality"),
            "ext": item.get("ext"),
            "format_id": item.get("format_id"),
            "download_url": item.get("download_url"),
            "type": item.get("type"),
        })

    return {
        "success": True,
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration_sec": info.get("duration_sec"),
        "website": info.get("website"),
        "selected_quality": selected.get("quality") if selected else None,
        "selected_ext": selected.get("ext") if selected else None,
        "download_url": selected.get("download_url") if selected else None,
        "format_id": selected.get("format_id") if selected else None,
        "best_format": selected,
        "formats": formats,
    }


@app.get("/")
def home():
    return {"status": "server chal raha hai ✅", "docs": "/docs"}


@app.get("/api/extract")
def extract(url: str = Query(..., description="Video ka URL paste karo"), quality: str | None = Query(None, description="Optional: 360p, 480p, 720p, 1080p")):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Galat URL. http:// ya https:// se shuru hona chahiye.")

    try:
        info = get_video_info(url)
        selected = _select_format(info.get("formats", []), quality)
        if selected:
            info["best_format"] = selected
            info["top_formats"] = [selected]
        return _build_mobile_payload(info, selected)
    except Exception as e:
        raise HTTPException(422, f"Video nahi mila: {str(e)[:150]}")


@app.get("/api/download")
def download(url: str = Query(..., description="Download karne ke liye video URL"), quality: str | None = Query(None, description="Optional: 360p, 480p, 720p, 1080p")):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Galat URL. http:// ya https:// se shuru hona chahiye.")

    try:
        info = get_video_info(url)
        selected = _select_format(info.get("formats", []), quality)
        if not selected:
            raise HTTPException(404, "Video ke liye koi quality format available nahi hai.")

        payload = _build_mobile_payload(info, selected)
        payload["quality"] = selected.get("quality")
        payload["ext"] = selected.get("ext")
        payload["type"] = selected.get("type")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Download link nahi bana: {str(e)[:150]}")


@app.get("/api/download-file")
def download_file(url: str = Query(..., description="Actual video file download karne ke liye URL"), quality: str | None = Query(None, description="Optional: 360p, 480p, 720p, 1080p")):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Galat URL. http:// ya https:// se shuru hona chahiye.")

    temp_dir = tempfile.mkdtemp(prefix="video_download_")
    try:
        downloaded_path = download_video(url, output_dir=temp_dir, quality=quality)
        if not os.path.exists(downloaded_path):
            raise FileNotFoundError("Downloaded file not found")
        return FileResponse(path=downloaded_path, filename=os.path.basename(downloaded_path), media_type="application/octet-stream")
    except Exception as exc:
        raise HTTPException(422, f"Video download fail hua: {str(exc)[:150]}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
