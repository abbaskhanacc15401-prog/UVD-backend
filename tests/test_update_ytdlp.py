import unittest

from scripts.update_ytdlp import (
    _https_remote_url,
    _replace_pin,
    _requirements_pin,
    _version_key,
)


class YtDlpUpdaterTests(unittest.TestCase):
    def test_reads_exact_pinned_requirement_and_preserves_extras(self):
        contents = (
            "fastapi==0.115.0\n"
            "yt-dlp[default,curl-cffi]==2026.8.19\n"
            "httpx==0.28.1\n"
        )

        prefix, version, suffix, _line = _requirements_pin(contents)

        self.assertEqual(prefix, "yt-dlp[default,curl-cffi]==")
        self.assertEqual(version, "2026.8.19")
        self.assertEqual(suffix, "\n")

    def test_replaces_only_yt_dlp_pin(self):
        contents = "yt-dlp[default,curl-cffi]==2026.8.19\nhttpx==0.28.1\n"

        self.assertEqual(
            _replace_pin(contents, "2026.10.9"),
            "yt-dlp[default,curl-cffi]==2026.10.9\nhttpx==0.28.1\n",
        )

    def test_version_comparison_uses_numeric_components(self):
        self.assertGreater(_version_key("2026.10.1"), _version_key("2026.9.99"))
        self.assertEqual(_version_key("1.2"), _version_key("1.2.0"))

    def test_github_ssh_remote_uses_https(self):
        self.assertEqual(
            _https_remote_url("git@github.com:owner/repo.git"),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            _https_remote_url("ssh://git@github.com/owner/repo.git"),
            "https://github.com/owner/repo.git",
        )


if __name__ == "__main__":
    unittest.main()
