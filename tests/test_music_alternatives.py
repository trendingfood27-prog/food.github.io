"""
tests/test_music_alternatives.py — Unit tests for src/music_alternatives.py

Tests the Incompetech and ccMixter download helpers without making real
network requests.

Run with: python -m pytest tests/ -v
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests as req

# Stub heavy optional imports not needed for these tests
for _mod in (
    "edge_tts",
    "moviepy", "moviepy.editor",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "pydub",
    "mutagen", "mutagen.mp3",
    "googleapiclient", "googleapiclient.discovery",
    "httpx",
):
    sys.modules.setdefault(_mod, MagicMock())


class TestDownloadIncompetech(unittest.TestCase):
    """Tests for music_alternatives.download_incompetech()."""

    def setUp(self):
        import src.music_alternatives as ma
        self.ma = ma

    def test_returns_cached_file_without_downloading(self):
        """If the output path already exists, no network request is made."""
        with patch("src.music_alternatives.requests.get") as mock_get, \
             patch("pathlib.Path.exists", return_value=True):
            result = self.ma.download_incompetech(
                "cooking", Path("/tmp/music"), "abc123"
            )
        mock_get.assert_not_called()
        self.assertIsNotNone(result)

    def test_falls_through_to_next_track_on_404(self):
        """If the first track returns 404, the next track in the list is tried."""
        mock_bad_resp = MagicMock()
        mock_bad_resp.raise_for_status.side_effect = req.HTTPError(
            response=MagicMock(status_code=404)
        )
        mock_bad_resp.__enter__ = lambda s: s
        mock_bad_resp.__exit__ = MagicMock(return_value=False)

        mock_good_resp = MagicMock()
        mock_good_resp.raise_for_status.return_value = None
        mock_good_resp.iter_content.return_value = [b"data"]
        mock_good_resp.__enter__ = lambda s: s
        mock_good_resp.__exit__ = MagicMock(return_value=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            with patch("src.music_alternatives.requests.get") as mock_get, \
                 patch("pathlib.Path.exists", return_value=False), \
                 patch("builtins.open", MagicMock()):
                mock_get.side_effect = [mock_bad_resp, mock_good_resp]
                result = self.ma.download_incompetech("cooking", cache_dir, "abc123")

        # Should have tried at least two tracks
        self.assertGreaterEqual(mock_get.call_count, 2)

    def test_returns_none_when_all_tracks_fail(self):
        """Returns None when every track in the list fails to download."""
        mock_bad_resp = MagicMock()
        mock_bad_resp.raise_for_status.side_effect = req.HTTPError(
            response=MagicMock(status_code=404)
        )
        mock_bad_resp.__enter__ = lambda s: s
        mock_bad_resp.__exit__ = MagicMock(return_value=False)

        cache_dir = Path("/tmp/test_incompetech_all_fail")
        with patch("src.music_alternatives.requests.get", return_value=mock_bad_resp), \
             patch("pathlib.Path.exists", return_value=False):
            result = self.ma.download_incompetech("cooking", cache_dir, "abc123")

        self.assertIsNone(result)

    def test_morning_routine_not_in_track_list(self):
        """The broken 'Morning Routine' URL has been removed from the track list."""
        tracks = self.ma._INCOMPETECH_TRACKS.get("cooking", [])
        titles = [t["title"] for t in tracks]
        self.assertNotIn("Morning Routine", titles)

    def test_track_lists_include_more_variety(self):
        """Incompetech pool includes an expanded set of tracks per mood."""
        self.assertGreaterEqual(len(self.ma._INCOMPETECH_TRACKS.get("cooking", [])), 5)
        self.assertGreaterEqual(len(self.ma._INCOMPETECH_TRACKS.get("upbeat", [])), 5)
        self.assertGreaterEqual(len(self.ma._INCOMPETECH_TRACKS.get("relaxed", [])), 3)
        self.assertGreaterEqual(len(self.ma._INCOMPETECH_TRACKS.get("reveal", [])), 3)


class TestDownloadCcMixterHttpNormalisation(unittest.TestCase):
    """Tests that ccMixter HTTPS download URLs are normalised to HTTP."""

    def setUp(self):
        import src.music_alternatives as ma
        self.ma = ma

    def test_https_ccmixter_url_normalised_to_http(self):
        """HTTPS ccmixter.org download URLs are converted to HTTP before use."""
        # Build a fake API response returning an HTTPS mp3 URL
        fake_track = {
            "upload_id": "99999",
            "upload_name": "Test Track",
            "files": [
                {"download_url": "https://ccmixter.org/content/artist/artist_-_song.mp3"}
            ],
        }

        mock_api_resp = MagicMock()
        mock_api_resp.raise_for_status.return_value = None
        mock_api_resp.json.return_value = [fake_track]

        mock_dl_resp = MagicMock()
        mock_dl_resp.raise_for_status.return_value = None
        mock_dl_resp.iter_content.return_value = [b"audio"]
        mock_dl_resp.__enter__ = lambda s: s
        mock_dl_resp.__exit__ = MagicMock(return_value=False)

        cache_dir = Path("/tmp/test_ccmixter_ssl")
        called_urls = []

        def fake_get(url, **kwargs):
            called_urls.append(url)
            if "api/query" in url:
                return mock_api_resp
            return mock_dl_resp

        with patch("src.music_alternatives.requests.get", side_effect=fake_get), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("builtins.open", MagicMock()):
            self.ma.download_ccmixter("cooking", cache_dir, "abc123")

        # The download request must use HTTP, not HTTPS
        download_calls = [u for u in called_urls if "content" in u]
        self.assertTrue(len(download_calls) > 0, "Expected at least one download call")
        for url in download_calls:
            self.assertTrue(
                url.startswith("http://"),
                f"Expected HTTP URL, got: {url}",
            )
            self.assertFalse(
                url.startswith("https://"),
                f"HTTPS URL was not normalised to HTTP: {url}",
            )


if __name__ == "__main__":
    unittest.main()
