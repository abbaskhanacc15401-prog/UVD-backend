import ipaddress
import os
import shutil
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.extractor import _select_download_format, download_media, get_video_info

app = FastAPI(
    title="Universal Video Downloader API",
    description="Extract legal, user-authorized media links and download MP4/audio files.",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _validate_source_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "URL must start with http:// or https://.")
    if parsed.username or parsed.password:
        raise HTTPException(400, "URLs containing a username or password are not supported.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise HTTPException(400, "Local network URLs are not supported.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError) as exc:
            raise HTTPException(400, "The source host could not be resolved.") from exc
        if not addresses or any(not address.is_global for address in addresses):
            raise HTTPException(400, "Private or reserved IP addresses are not supported.")
    else:
        if not address.is_global:
            raise HTTPException(400, "Private or reserved IP addresses are not supported.")


def _file_download_url(
    request: Request,
    *,
    source_url: str,
    quality: str | None = None,
    format_id: str | None = None,
    kind: str = "video",
) -> str:
    params = {"url": source_url, "kind": kind}
    if quality:
        params["quality"] = quality
    if format_id:
        params["format_id"] = format_id
    return f"{request.base_url}api/download-file?{urlencode(params)}"


def _build_payload(request: Request, info: dict, quality: str | None) -> dict:
    public_formats = []
    for item in info["formats"]:
        kind = item["type"]
        item_quality = item["quality"]
        format_url = _file_download_url(
            request,
            source_url=request.query_params["url"],
            quality=item_quality if kind != "audio-only" else None,
            format_id=item["format_id"] if kind == "audio-only" else None,
            kind="audio" if kind == "audio-only" else "video",
        )
        public_formats.append(
            {
                "quality": item_quality,
                "ext": "mp4" if kind != "audio-only" else item["ext"],
                "format_id": item["format_id"],
                "download_url": format_url,
                "audio_url": format_url if kind == "audio-only" else None,
                "type": kind,
                "filesize_mb": item["filesize_mb"],
            }
        )

    video_formats = [item for item in public_formats if item["type"] != "audio-only"]
    audio_formats = [item for item in public_formats if item["type"] == "audio-only"]
    selected = _select_download_format(video_formats, quality)
    selected_audio = audio_formats[0] if audio_formats else None
    return {
        "success": bool(video_formats or audio_formats),
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration_sec": info["duration_sec"],
        "website": info["website"],
        "selected_quality": selected["quality"] if selected else None,
        "selected_ext": "mp4" if selected else None,
        "download_url": selected["download_url"] if selected else None,
        "audio_url": selected_audio["download_url"] if selected_audio else None,
        "format_id": selected["format_id"] if selected else None,
        "formats": public_formats,
    }


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "Backend chal raha hai", "docs": "/docs", "app": "/"}


@app.get("/api/extract")
def extract(
    request: Request,
    url: str = Query(..., description="Video ka public URL"),
    quality: str | None = Query(None, description="Misal: 360p, 720p, 1080p"),
) -> dict:
    _validate_source_url(url)
    try:
        info = get_video_info(url)
    except Exception as exc:
        raise HTTPException(422, f"Video information could not be read: {str(exc)[:200]}") from exc
    return _build_payload(request, info, quality)


@app.get("/api/download")
def download(
    request: Request,
    url: str = Query(..., description="Video ka public URL"),
    quality: str | None = Query(None, description="Misal: 360p, 720p, 1080p"),
) -> dict:
    return extract(request, url, quality)


@app.get("/api/download-file", name="download_file")
def download_file(
    url: str = Query(..., description="Original video URL"),
    quality: str | None = Query(None, description="Video quality, for example 720p"),
    kind: str = Query("video", pattern="^(video|audio)$"),
    format_id: str | None = Query(None, max_length=100),
) -> FileResponse:
    _validate_source_url(url)
    temp_dir = tempfile.mkdtemp(prefix="uvd-download-")
    try:
        path, filename = download_media(
            url,
            temp_dir,
            quality=quality,
            format_id=format_id,
            kind=kind,
        )
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(422, f"Media download failed: {str(exc)[:200]}") from exc

    media_type = "audio/" + Path(filename).suffix.lstrip(".") if kind == "audio" else "video/mp4"
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
    )
