import os
import re

import yt_dlp


def _build_ytdlp_options(client: str | None = None, *, download: bool = False):
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": not download,
        "retries": 2,
        "socket_timeout": 20,
        "extractor_args": {},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if client and client != "default":
        options["extractor_args"] = {"youtube": [f"player_client={client}"]}

    return options


def _extract_with_fallbacks(url: str, *, download: bool = False):
    last_error = None
    for client in ["default", "web", "android", "mweb", "tv_embedded"]:
        try:
            options = _build_ytdlp_options(client, download=download)
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=download)
            if isinstance(info, dict) and info.get("title"):
                return info
            if isinstance(info, list) and info:
                return info[0]
            if info is not None:
                return info
        except Exception as exc:  # pragma: no cover - fallback path for real network failures
            last_error = exc
            continue

    raise last_error or RuntimeError("Could not extract video metadata")


def _quality_sort_key(value):
    if not value:
        return 0

    match = re.search(r"(\d{3,4})p", str(value), re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)x(\d+)", str(value), re.IGNORECASE)
    if match:
        return max(int(match.group(1)), int(match.group(2)))

    if str(value).lower() in {"tiny", "small", "medium", "large", "hd720", "hd1080"}:
        mapping = {
            "tiny": 144,
            "small": 360,
            "medium": 480,
            "large": 720,
            "hd720": 720,
            "hd1080": 1080,
        }
        return mapping.get(str(value).lower(), 0)

    return 0


def _resolve_quality_label(format_item):
    for key in ("quality_label", "resolution", "format_note", "quality"):
        value = format_item.get(key)
        if value:
            text = str(value).strip()
            if text.lower() not in {"n/a", "unknown"}:
                return text

    height = format_item.get("height")
    if isinstance(height, (int, float)) and height > 0:
        return f"{int(height)}p"

    width = format_item.get("width")
    if isinstance(width, (int, float)) and width > 0:
        return f"{int(width)}p"

    return "N/A"


def _select_download_format(formats, preferred_quality: str | None = None):
    if not formats:
        return None

    if preferred_quality:
        preferred = preferred_quality.lower()
        matches = [f for f in formats if preferred in str(f.get("quality", "")).lower()]
        if matches:
            return max(matches, key=lambda item: _quality_sort_key(item.get("quality")))

    return max(formats, key=lambda item: _quality_sort_key(item.get("quality")))


def _filter_formats(formats):
    filtered = []
    seen = set()

    for f in formats:
        if not f.get("url"):
            continue
        if f.get("format_id", "").startswith("sb"):
            continue
        if f.get("ext") in {"mhtml", "unknown"}:
            continue
        if f.get("vcodec") == "none" and f.get("acodec") == "none":
            continue
        if f.get("vcodec") == "none" and f.get("acodec") != "none":
            continue

        ext = (f.get("ext") or "").lower()
        if ext and ext not in {"mp4", "webm", "m4a"}:
            continue

        quality = _resolve_quality_label(f)
        quality_key = str(quality).lower()
        if not quality_key or quality_key == "n/a":
            continue

        # Remove duplicate stream variants and keep only practical quality buckets.
        score = _quality_sort_key(quality)
        if score < 240 and quality_key not in {"tiny", "small", "medium", "large", "hd720", "hd1080"}:
            continue

        dedupe_key = (quality_key, ext)
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        filtered.append(
            {
                "format_id": f["format_id"],
                "quality": quality,
                "ext": ext or f.get("ext"),
                "filesize_mb": round(f["filesize"] / 1024 / 1024, 2) if f.get("filesize") else None,
                "download_url": f["url"],
                "type": "video+audio" if f.get("vcodec") != "none" and f.get("acodec") != "none" else "video-only",
            }
        )

    filtered.sort(key=lambda x: _quality_sort_key(x["quality"]), reverse=True)

    # Keep response compact and mobile-useful instead of every single yt-dlp variant.
    limited = []
    seen_qualities = set()
    for item in filtered:
        q = str(item["quality"]).lower()
        if q in seen_qualities:
            continue
        seen_qualities.add(q)
        limited.append(item)
        if len(limited) >= 8:
            break

    return limited


def _build_download_format_candidates(quality: str | None = None):
    candidates = [
        "best[ext=mp4]/best",
        "bestvideo+bestaudio/best",
        "bestvideo+bestaudio",
        "best",
    ]

    if quality:
        parsed = _quality_sort_key(quality)
        if parsed:
            candidates = [
                f"best[height<={parsed}][ext=mp4]/best[height<={parsed}]/best",
                f"best[height<={parsed}]/best",
                f"bestvideo[height<={parsed}][ext=mp4]+bestaudio[ext=m4a]/best[height<={parsed}]/best",
                *candidates,
            ]

    deduped = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def download_video(url: str, output_dir: str = ".", quality: str | None = None, progress_hook=None):
    os.makedirs(output_dir, exist_ok=True)

    last_error = None
    for candidate in _build_download_format_candidates(quality):
        options = {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "format": candidate,
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook] if progress_hook else [],
            "merge_output_format": "mp4",
            "socket_timeout": 20,
            "retries": 2,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
            title = (info or {}).get("title") or "video"
            ext = (info or {}).get("ext") or "mp4"
            return os.path.join(output_dir, f"{title}.{ext}")
        except Exception as exc:  # pragma: no cover - fallback path for real network errors
            last_error = exc
            continue

    raise last_error or RuntimeError("No working download format found for this video")


def get_video_info(url: str):
    """
    URL se video ki info nikalta hai bina download kiye.
    Returns: title, thumbnail, duration, formats (download links)
    """
    info = _extract_with_fallbacks(url, download=False)
    if not isinstance(info, dict):
        raise RuntimeError("Could not extract video metadata")

    filtered_formats = _filter_formats(info.get("formats", []))

    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration_sec": info.get("duration"),
        "website": info.get("extractor_key"),
        "best_format": filtered_formats[0] if filtered_formats else None,
        "top_formats": filtered_formats[:5],
        "formats": filtered_formats,
    }
