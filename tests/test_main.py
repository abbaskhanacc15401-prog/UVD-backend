import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import extractor
from app.main import app


class ExtractorTests(unittest.TestCase):
    def test_filters_video_quality_and_keeps_audio_formats(self):
        formats = [
            {
                "format_id": "22",
                "height": 720,
                "ext": "mp4",
                "url": "video",
                "vcodec": "avc1",
                "acodec": "mp4a",
            },
            {
                "format_id": "251",
                "ext": "webm",
                "url": "audio",
                "vcodec": "none",
                "acodec": "opus",
            },
        ]

        filtered = extractor._filter_formats(formats)

        self.assertEqual([item["quality"] for item in filtered], ["720p", "audio"])
        self.assertEqual(filtered[1]["type"], "audio-only")

    def test_selects_requested_or_nearest_lower_quality(self):
        formats = [
            {"format_id": "18", "quality": "360p", "type": "video+audio"},
            {"format_id": "22", "quality": "720p", "type": "video+audio"},
            {"format_id": "137", "quality": "1080p", "type": "video-only"},
        ]

        self.assertEqual(extractor._select_download_format(formats, "720p")["format_id"], "22")
        self.assertEqual(extractor._select_download_format(formats, "800p")["format_id"], "22")
        self.assertEqual(extractor._select_download_format(formats)["format_id"], "137")

    def test_video_download_options_select_mp4_and_merge_audio(self):
        from pathlib import Path

        options = extractor._download_options(Path("C:\\temp"), quality="720p")

        self.assertIn("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]", options["format"])
        self.assertEqual(options["merge_output_format"], "mp4")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_rejects_localhost_source_url(self):
        response = self.client.get(
            "/api/download",
            params={"url": "http://localhost/private"},
        )

        self.assertEqual(response.status_code, 400)

    def test_root_serves_pc_download_tester(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Video Download Tester", response.text)
        self.assertIn("/api/download?", response.text)

    @patch("app.main.get_video_info")
    def test_returns_quality_and_audio_download_links(self, get_video_info):
        get_video_info.return_value = {
            "title": "Demo",
            "thumbnail": None,
            "duration_sec": 45,
            "website": "demo",
            "formats": [
                {
                    "format_id": "22",
                    "quality": "720p",
                    "ext": "mp4",
                    "filesize_mb": None,
                    "type": "video+audio",
                },
                {
                    "format_id": "251",
                    "quality": "audio",
                    "ext": "m4a",
                    "filesize_mb": None,
                    "type": "audio-only",
                },
            ],
        }

        response = self.client.get(
            "/api/download",
            params={"url": "https://8.8.8.8/video", "quality": "720p"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_ext"], "mp4")
        self.assertIn("/api/download-file?", payload["download_url"])
        self.assertIn("kind=audio", payload["audio_url"])
        self.assertEqual(len(payload["formats"]), 2)

    @patch("app.main.download_media")
    def test_download_file_returns_mp4_response(self, download_media):
        def create_file(_url, output_dir, **_options):
            filepath = Path(output_dir) / "demo.mp4"
            filepath.write_bytes(b"mp4-data")
            return str(filepath), filepath.name

        download_media.side_effect = create_file

        response = self.client.get(
            "/api/download-file",
            params={"url": "https://8.8.8.8/video", "quality": "720p"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"mp4-data")
        self.assertTrue(response.headers["content-type"].startswith("video/mp4"))
