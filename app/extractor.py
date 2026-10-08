import os
import re
from pathlib import Path
from typing import Any

import yt_dlp


def _build_ytdlp_options(client: str | None = None, *, download: bool = False) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": not download,
        "retries": 2,
        "socket_timeout": 20,
    }
    if client and client != "default":
        options["extractor_args"] = {"youtube": [f"player_client={client}"]}
    return options


def _extract_with_fallbacks(url: str, *, download: bool = False) -> dict[str, Any]:
    last_error: Exception | None = None
    for client in ("default", "web", "android", "mweb", "tv_embedded"):
        try:
            with yt_dlp.YoutubeDL(_build_ytdlp_options(client, download=download)) as ydl:
                info = ydl.extract_info(url, download=download)
            if isinstance(info, list):
                info = info[0] if info else None
            if isinstance(info, dict):
                return info
        except Exception as exc:
            last_error = exc

    raise last_error or RuntimeError("Video metadata could not be extracted")


def _quality_sort_key(value: Any) -> int:
    if not value:
        return 0
    text = str(value)
    match = re.search(r"(\d{3,4})p", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)x(\d+)", text, re.IGNORECASE)
    if match:
        return max(int(match.group(1)), int(match.group(2)))
    return {
        "tiny": 144,
        "small": 360,
        "medium": 480,
        "large": 720,
        "hd720": 720,
        "hd1080": 1080,
    }.get(text.lower(), 0)


def _resolve_quality_label(item: dict[str, Any]) -> str:
    height = item.get("height")
    if isinstance(height, (int, float)) and height > 0:
        return f"{int(height)}p"
    for key in ("quality_label", "resolution", "format_note", "quality"):
        value = item.get(key)
        if value and str(value).lower() not in {"n/a", "unknown"}:
            return str(value).strip()
    return "N/A"


def _get_format_type(item: dict[str, Any]) -> str:
    video = str(item.get("vcodec") or "none").lower() != "none"
    audio = str(item.get("acodec") or "none").lower() != "none"
    if video and audio:
        return "video+audio"
    if video:
        return "video-only"
    if audio:
        return "audio-only"
    return "unknown"


def _filter_formats(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    video_formats: list[dict[str, Any]] = []
    audio_formats: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for item in formats:
        source_url = item.get("url")
        format_id = item.get("format_id")
        ext = str(item.get("ext") or "").lower()
        kind = _get_format_type(item)
        if not source_url or not format_id or str(format_id).startswith("sb"):
            continue
        if ext not in {"mp4", "webm", "m4a"} or kind == "unknown":
            continue

        quality = _resolve_quality_label(item)
        if kind != "audio-only" and _quality_sort_key(quality) < 240:
            continue
        if quality == "N/A":
            quality = "audio" if kind == "audio-only" else quality

        key = (quality.lower(), ext, kind)
        if key in seen:
            continue
        seen.add(key)

        entry = {
            "format_id": str(format_id),
            "quality": quality,
            "ext": ext,
            "abr": item.get("abr") or 0,
            "filesize_mb": round(item["filesize"] / 1024 / 1024, 2)
            if item.get("filesize")
            else None,
            "source_url": source_url,
            "type": kind,
        }
        (audio_formats if kind == "audio-only" else video_formats).append(entry)

    video_formats.sort(key=lambda entry: _quality_sort_key(entry["quality"]), reverse=True)
    audio_formats.sort(key=lambda entry: entry["abr"], reverse=True)
    return video_formats[:8] + audio_formats[:3]


def _select_download_format(
    formats: list[dict[str, Any]], preferred_quality: str | None = None
) -> dict[str, Any] | None:
    video_formats = [item for item in formats if item.get("type") != "audio-only"]
    if not video_formats:
        return None
    if preferred_quality:
        preferred = preferred_quality.strip().lower()
        exact_matches = [
            item for item in video_formats if str(item.get("quality", "")).lower() == preferred
        ]
        if exact_matches:
            return exact_matches[0]
        requested_height = _quality_sort_key(preferred)
        if requested_height:
            at_or_below = [
                item
                for item in video_formats
                if _quality_sort_key(item.get("quality")) <= requested_height
            ]
            if at_or_below:
                return max(at_or_below, key=lambda item: _quality_sort_key(item["quality"]))
    return max(video_formats, key=lambda item: _quality_sort_key(item.get("quality")))


def _download_options(
    output_dir: Path,
    *,
    quality: str | None = None,
    format_id: str | None = None,
    kind: str = "video",
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 2,
        "socket_timeout": 20,
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
    }
    if kind == "audio":
        if not format_id:
            raise ValueError("Audio download requires a format ID")
        options["format"] = format_id
    else:
        height = _quality_sort_key(quality) if quality else 0
        cap = f"[height<={height}]" if height else ""
        options["format"] = (
            f"bestvideo{cap}[ext=mp4]+bestaudio[ext=m4a]/"
            f"best{cap}[ext=mp4]"
        )
        options["merge_output_format"] = "mp4"
    return options


def download_media(
    url: str,
    output_dir: str,
    *,
    quality: str | None = None,
    format_id: str | None = None,
    kind: str = "video",
) -> tuple[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if kind == "audio":
        audio_formats = [
            item
            for item in get_video_info(url)["formats"]
            if item["type"] == "audio-only"
        ]
        if not any(item["format_id"] == format_id for item in audio_formats):
            raise ValueError("The requested audio format is not available for this media")
    options = _download_options(directory, quality=quality, format_id=format_id, kind=kind)

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    if not isinstance(info, dict):
        raise RuntimeError("Downloaded file information is unavailable")
    filepath = info.get("filepath")
    if not filepath:
        filepath = next(
            (str(path) for path in directory.iterdir() if path.is_file()),
            None,
        )
    if not filepath or not os.path.isfile(filepath):
        raise FileNotFoundError("Downloaded file was not created")
    filename = Path(filepath).name
    return filepath, filename


def get_video_info(url: str) -> dict[str, Any]:
    info = _extract_with_fallbacks(url)
    formats = _filter_formats(info.get("formats") or [])
    return {
        "title": info.get("title") or "Video",
        "thumbnail": info.get("thumbnail"),
        "duration_sec": info.get("duration"),
        "website": info.get("extractor_key"),
        "formats": formats,
    }
