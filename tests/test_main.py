import unittest

from app.extractor import _filter_formats


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


if __name__ == "__main__":
    unittest.main()
