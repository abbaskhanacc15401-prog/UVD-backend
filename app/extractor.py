import re

import yt_dlp


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

        quality = f.get("resolution") or f.get("format_note") or "N/A"
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


def get_video_info(url: str):
    """
    URL se video ki info nikalta hai bina download kiye.
    Returns: title, thumbnail, duration, formats (download links)
    """
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

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
