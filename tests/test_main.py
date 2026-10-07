import unittest
from unittest.mock import patch

from app import extractor
from app.extractor import _filter_formats, _select_download_format


class ExtractorFormatFilterTests(unittest.TestCase):
    def test_filters_duplicate_and_low_quality_formats(self):
        formats = [
            {"format_id": "602", "resolution": "256x144", "ext": "mp4", "url": "u1", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "269", "resolution": "256x144", "ext": "mp4", "url": "u2", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "229", "resolution": "426x240", "ext": "mp4", "url": "u3", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "230", "resolution": "640x360", "ext": "mp4", "url": "u4", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "231", "resolution": "854x480", "ext": "mp4", "url": "u5", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "232", "resolution": "1280x720", "ext": "mp4", "url": "u6", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "137", "resolution": "1920x1080", "ext": "mp4", "url": "u7", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "138", "resolution": "1920x1080", "ext": "mp4", "url": "u8", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "251", "resolution": "N/A", "format_note": "tiny", "ext": "webm", "url": "u9", "vcodec": "none", "acodec": "opus"},
        ]

        filtered = _filter_formats(formats)

        self.assertLessEqual(len(filtered), 8)
        self.assertEqual(filtered[0]["quality"], "1920x1080")
        self.assertNotIn("tiny", {item["quality"] for item in filtered})

    def test_selects_best_download_format_by_quality(self):
        formats = [
            {"format_id": "18", "quality": "360p", "ext": "mp4"},
            {"format_id": "22", "quality": "720p", "ext": "mp4"},
            {"format_id": "137", "quality": "1080p", "ext": "mp4"},
        ]

        selected = _select_download_format(formats, "720p")

        self.assertEqual(selected["format_id"], "22")

    def test_keeps_mp4_formats_that_use_height_or_quality_label(self):
        formats = [
            {"format_id": "248", "ext": "mp4", "url": "u1", "vcodec": "avc1", "acodec": "mp4a", "height": 1080},
            {"format_id": "251", "ext": "webm", "url": "u2", "vcodec": "none", "acodec": "opus", "height": 0},
        ]

        filtered = _filter_formats(formats)

        self.assertTrue(filtered)
        self.assertEqual(filtered[0]["quality"], "1080p")
        self.assertEqual(filtered[0]["download_url"], "u1")

    def test_extract_with_fallbacks_tries_multiple_youtube_clients(self):
        fake_calls = []

        class FakeYDL:
            def __init__(self, options):
                fake_calls.append(options)
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, url, download=False):
                if self.options.get("extractor_args", {}).get("youtube") == ["player_client=web"]:
                    raise RuntimeError("web client blocked")
                return {"title": "demo", "formats": []}

        with patch.object(extractor.yt_dlp, "YoutubeDL", side_effect=lambda options: FakeYDL(options)):
            info = extractor._extract_with_fallbacks("https://example.com", download=False)

        self.assertEqual(info["title"], "demo")
        self.assertGreaterEqual(len(fake_calls), 2)


if __name__ == "__main__":
    unittest.main()
