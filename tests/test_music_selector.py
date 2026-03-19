"""
tests/test_music_selector.py — Unit tests for src/music_selector.py

Tests scene classification, mood mapping, and music selection logic without
making any real API calls.

Run with: python -m pytest tests/ -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub heavy optional imports not needed for music_selector tests
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


class TestClassifySceneType(unittest.TestCase):
    """Tests for music_selector.classify_scene_type()."""

    def setUp(self):
        from src.music_selector import classify_scene_type
        self.classify = classify_scene_type

    def test_first_scene_is_intro(self):
        self.assertEqual(self.classify(0, 4), "intro")

    def test_last_scene_is_punchline(self):
        self.assertEqual(self.classify(3, 4), "punchline")

    def test_middle_scenes_are_middle(self):
        self.assertEqual(self.classify(1, 4), "middle")
        self.assertEqual(self.classify(2, 4), "middle")

    def test_single_scene_is_middle(self):
        self.assertEqual(self.classify(0, 1), "middle")

    def test_zero_scenes_is_middle(self):
        self.assertEqual(self.classify(0, 0), "middle")

    def test_two_scenes_intro_and_punchline(self):
        self.assertEqual(self.classify(0, 2), "intro")
        self.assertEqual(self.classify(1, 2), "punchline")

    def test_three_scenes_intro_middle_punchline(self):
        self.assertEqual(self.classify(0, 3), "intro")
        self.assertEqual(self.classify(1, 3), "middle")
        self.assertEqual(self.classify(2, 3), "punchline")


class TestGetMoodForScene(unittest.TestCase):
    """Tests for music_selector.get_mood_for_scene()."""

    def setUp(self):
        from src.music_selector import get_mood_for_scene
        self.get_mood = get_mood_for_scene

    def test_intro_returns_non_empty_string(self):
        mood = self.get_mood("intro")
        self.assertIsInstance(mood, str)
        self.assertTrue(mood.strip(), "mood query must not be blank")

    def test_middle_returns_non_empty_string(self):
        mood = self.get_mood("middle")
        self.assertIsInstance(mood, str)
        self.assertTrue(mood.strip())

    def test_punchline_returns_non_empty_string(self):
        mood = self.get_mood("punchline")
        self.assertIsInstance(mood, str)
        self.assertTrue(mood.strip())

    def test_unknown_scene_type_falls_back_to_middle_moods(self):
        """An unrecognised scene type should not raise; it falls back to 'middle'."""
        mood = self.get_mood("unknown_scene_xyz")
        self.assertIsInstance(mood, str)
        self.assertTrue(mood.strip())

    def test_all_scene_types_contain_descriptive_keywords(self):
        """Each mood query should be descriptive enough to use as a search term."""
        for scene_type in ("intro", "middle", "punchline"):
            mood = self.get_mood(scene_type)
            self.assertGreater(len(mood.split()), 1,
                               f"mood for '{scene_type}' should be multi-word: '{mood}'")


class TestGetMusicForScenes(unittest.TestCase):
    """Tests for music_selector.get_music_for_scenes()."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_returns_none_when_music_disabled(self):
        with patch.object(self.ms.config, "MUSIC_ENABLED", False):
            result = self.ms.get_music_for_scenes(["intro scene"], "pasta")
        self.assertIsNone(result)

    def test_returns_silence_fallback_without_freesound_api_key(self):
        """With no API key and empty cache, a silence fallback path is returned."""
        fake_silence_path = Path("/tmp/cache/testkey_silence.wav")
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", None), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache_empty"), \
             patch("src.music_selector._download_from_free_music_archive",
                   return_value=None), \
             patch("src.music_selector._download_from_incompetech",
                   return_value=None), \
             patch("src.music_selector._download_from_ccmixter",
                   return_value=None), \
             patch("src.music_selector._get_local_cached_track",
                   return_value=None), \
             patch("src.music_selector._create_silence_fallback",
                   return_value=fake_silence_path) as mock_silence, \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes(["intro scene"], "pasta")
        mock_silence.assert_called_once()
        self.assertEqual(result, fake_silence_path)
        self.assertTrue(str(result).endswith("_silence.wav"))

    def test_returns_cached_file_when_available(self):
        """If a matching file is already in the cache, it is returned immediately."""
        fake_cached_path = Path("/tmp/cache/abc123_456.mp3")
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache"), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = [fake_cached_path]
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes(["cooking scene"], "chicken tikka")
        self.assertEqual(result, fake_cached_path)

    def test_calls_freesound_download_when_api_key_set(self):
        """When FREESOUND_API_KEY is present and all higher-priority sources fail, Freesound is queried."""
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache"), \
             patch("src.music_selector._download_from_pixabay",
                   return_value=None), \
             patch("src.music_selector._download_from_free_music_archive",
                   return_value=None), \
             patch("src.music_selector._download_from_freesound",
                   return_value=None) as mock_dl, \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            self.ms.get_music_for_scenes(["baking scene"], "pizza")
        mock_dl.assert_called_once()

    def test_returns_downloaded_path_from_freesound(self):
        """If Freesound download succeeds, the returned path is passed through."""
        fake_music_path = Path("/tmp/cache/xyz_789.mp3")
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache"), \
             patch("src.music_selector._download_from_pixabay", return_value=None), \
             patch("src.music_selector._download_from_free_music_archive", return_value=None), \
             patch("src.music_selector._download_from_freesound",
                   return_value=fake_music_path), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes(["stir fry scene"], "noodles")
        self.assertEqual(result, fake_music_path)

    def test_handles_empty_scenes_list(self):
        """An empty scene list should not raise an exception."""
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", None), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache"), \
             patch("src.music_selector._download_from_free_music_archive",
                   return_value=None), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes([], "")
        self.assertIsNotNone(result)

    def test_returns_none_when_all_music_sources_fail(self):
        """When all sources are unavailable and silence fallback also fails, returns None."""
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", None), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache_empty"), \
             patch("src.music_selector._download_from_free_music_archive", return_value=None), \
             patch("src.music_selector._download_from_incompetech", return_value=None), \
             patch("src.music_selector._download_from_ccmixter", return_value=None), \
             patch("src.music_selector._get_local_cached_track", return_value=None), \
             patch("src.music_selector._create_silence_fallback", return_value=None), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes(["intro scene"], "pasta")
        self.assertIsNone(result)

    def test_default_priority_does_not_use_free_music_archive(self):
        """Default source chain should skip Free Music Archive entirely."""
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "PIXABAY_API_KEY", None), \
             patch.object(self.ms.config, "FREESOUND_API_KEY", None), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache_empty"), \
             patch("src.music_selector._download_from_free_music_archive", return_value=None) as mock_fma, \
             patch("src.music_selector._download_from_incompetech", return_value=None), \
             patch("src.music_selector._download_from_ccmixter", return_value=None), \
             patch("src.music_selector._get_local_cached_track", return_value=None), \
             patch("src.music_selector._create_silence_fallback", return_value=Path("/tmp/silence.wav")), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = []
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            self.ms.get_music_for_scenes(["intro scene"], "pasta")

        mock_fma.assert_not_called()


class TestDownloadFromFreesound(unittest.TestCase):
    """Tests for music_selector._download_from_freesound()."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_returns_none_without_api_key(self):
        with patch.object(self.ms.config, "FREESOUND_API_KEY", None):
            result = self.ms._download_from_freesound(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_on_api_error(self):
        with patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get",
                   side_effect=Exception("network error")):
            result = self.ms._download_from_freesound(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_results(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_freesound(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_preview_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"id": 1, "name": "test", "previews": {}}]
        }
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_freesound(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_downloads_preview_and_returns_path(self):
        """When results include a preview URL, the file is downloaded."""
        search_resp = MagicMock()
        search_resp.raise_for_status.return_value = None
        search_resp.json.return_value = {
            "results": [{
                "id": 42,
                "name": "Happy Cooking Loop",
                "previews": {"preview-hq-mp3": "https://cdn.freesound.org/42.mp3"},
            }]
        }

        download_resp = MagicMock()
        download_resp.raise_for_status.return_value = None
        download_resp.iter_content.return_value = [b"fake_mp3_data"]
        download_resp.__enter__ = MagicMock(return_value=download_resp)
        download_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(self.ms.config, "FREESOUND_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get",
                   side_effect=[search_resp, download_resp]), \
             patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            cache_dir = MagicMock(spec=Path)
            cache_dir.__truediv__ = MagicMock(
                return_value=Path("/tmp/cachekey_42.mp3")
            )
            result = self.ms._download_from_freesound(
                "happy cooking", cache_dir, "cachekey"
            )
        self.assertIsNotNone(result)


class TestCreateSilenceFallback(unittest.TestCase):
    """Tests for music_selector._create_silence_fallback()."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_creates_wav_file_in_cache_dir(self):
        """A WAV silence file is created in the provided cache directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            result = self.ms._create_silence_fallback(cache_dir, "testkey")
        self.assertIsNotNone(result)
        self.assertTrue(str(result).endswith(".wav"))

    def test_reuses_existing_silence_file(self):
        """If a silence file already exists it is returned without re-writing."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            first = self.ms._create_silence_fallback(cache_dir, "reusekey")
            self.assertIsNotNone(first)
            mtime_before = first.stat().st_mtime
            second = self.ms._create_silence_fallback(cache_dir, "reusekey")
            self.assertEqual(first, second)
            self.assertEqual(mtime_before, second.stat().st_mtime)

    def test_returns_none_on_write_failure(self):
        """Returns None gracefully when the WAV file cannot be written."""
        mock_dir = MagicMock(spec=Path)
        fake_path = MagicMock(spec=Path)
        fake_path.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=fake_path)
        with patch("src.music_selector.wave.open", side_effect=OSError("disk full")):
            result = self.ms._create_silence_fallback(mock_dir, "failkey")
        self.assertIsNone(result)

    def test_silence_file_is_valid_wav(self):
        """The generated file is a valid WAV that Python's wave module can read."""
        import tempfile
        import wave as _wave
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            result = self.ms._create_silence_fallback(cache_dir, "validwav")
            self.assertIsNotNone(result)
            with _wave.open(str(result), "r") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertGreater(wf.getnframes(), 0)


class TestDownloadFromPixabay(unittest.TestCase):
    """Tests for music_selector._download_from_pixabay()."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_returns_none_without_api_key(self):
        with patch.object(self.ms.config, "PIXABAY_API_KEY", None):
            result = self.ms._download_from_pixabay(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_on_api_error(self):
        with patch.object(self.ms.config, "PIXABAY_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get",
                   side_effect=Exception("network error")):
            result = self.ms._download_from_pixabay(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_hits(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": []}
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.ms.config, "PIXABAY_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_pixabay(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_audio_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hits": [{"id": 1, "pageURL": "https://pixabay.com/music/1"}]
        }
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.ms.config, "PIXABAY_API_KEY", "test_key"), \
             patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_pixabay(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)


class TestDownloadFromFreeMusicArchive(unittest.TestCase):
    """Tests for music_selector._download_from_free_music_archive()."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_returns_none_on_api_error(self):
        with patch("src.music_selector.requests.get",
                   side_effect=Exception("network error")):
            result = self.ms._download_from_free_music_archive(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_tracks(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"aTracks": []}
        mock_resp.raise_for_status.return_value = None
        with patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_free_music_archive(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_returns_none_when_no_download_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "aTracks": [{"track_id": "1", "track_title": "Test Track"}]
        }
        mock_resp.raise_for_status.return_value = None
        with patch("src.music_selector.requests.get", return_value=mock_resp):
            result = self.ms._download_from_free_music_archive(
                "test query", Path("/tmp"), "cachekey"
            )
        self.assertIsNone(result)

    def test_downloads_track_and_returns_path(self):
        """When a valid track_file URL is present, the file is downloaded."""
        search_resp = MagicMock()
        search_resp.raise_for_status.return_value = None
        search_resp.json.return_value = {
            "aTracks": [{
                "track_id": "99",
                "track_title": "Cooking Groove",
                "track_file": "https://files.freemusicarchive.org/99.mp3",
            }]
        }

        download_resp = MagicMock()
        download_resp.raise_for_status.return_value = None
        download_resp.iter_content.return_value = [b"fake_mp3_data"]
        download_resp.__enter__ = MagicMock(return_value=download_resp)
        download_resp.__exit__ = MagicMock(return_value=False)

        with patch("src.music_selector.requests.get",
                   side_effect=[search_resp, download_resp]), \
             patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            cache_dir = MagicMock(spec=Path)
            cache_dir.__truediv__ = MagicMock(
                return_value=Path("/tmp/cachekey_fma_99.mp3")
            )
            result = self.ms._download_from_free_music_archive(
                "cooking groove", cache_dir, "cachekey"
            )
        self.assertIsNotNone(result)

    def test_uses_percent_encoding_for_spaces(self):
        """The FMA request URL must use %20 for spaces, not +."""
        captured_urls = []

        def _capture(url, **kwargs):
            captured_urls.append(url)
            raise Exception("stop after capture")

        with patch("src.music_selector.requests.get", side_effect=_capture):
            self.ms._download_from_free_music_archive(
                "cooking groove", Path("/tmp"), "cachekey"
            )

        self.assertTrue(captured_urls, "requests.get was not called")
        self.assertIn("%20", captured_urls[0],
                      "spaces should be encoded as %20 in the FMA request URL")
        self.assertNotIn("+", captured_urls[0].split("?")[1],
                         "spaces must not be encoded as + in the FMA request URL")

    def test_retries_on_429_and_eventually_returns_none(self):
        """HTTP 429 responses trigger retries; returns None after max retries."""
        import requests as _requests

        http_error = _requests.HTTPError(response=MagicMock(status_code=429))
        with patch("src.music_selector.requests.get", side_effect=http_error), \
             patch("src.music_selector.time.sleep") as mock_sleep:
            result = self.ms._download_from_free_music_archive(
                "cooking groove", Path("/tmp"), "cachekey"
            )

        self.assertIsNone(result)
        # sleep is called on every retry attempt (all _FMA_MAX_RETRIES of them)
        self.assertEqual(mock_sleep.call_count, self.ms._FMA_MAX_RETRIES)

    def test_no_retry_on_404(self):
        """HTTP 404 is a permanent error; must not trigger retries."""
        import requests as _requests

        http_error = _requests.HTTPError(response=MagicMock(status_code=404))
        with patch("src.music_selector.requests.get", side_effect=http_error), \
             patch("src.music_selector.time.sleep") as mock_sleep:
            result = self.ms._download_from_free_music_archive(
                "bad query", Path("/tmp"), "cachekey"
            )

        self.assertIsNone(result)
        mock_sleep.assert_not_called()


class TestSanitizeTopic(unittest.TestCase):
    """Tests for music_selector._sanitize_topic()."""

    def setUp(self):
        from src.music_selector import _sanitize_topic
        self.sanitize = _sanitize_topic

    def test_removes_special_characters(self):
        """Special characters are replaced with spaces and collapsed."""
        self.assertEqual(self.sanitize("london vs arsenal"), "london vs arsenal")
        self.assertEqual(self.sanitize("pasta & sauce!"), "pasta sauce")
        self.assertEqual(self.sanitize("fish 'n' chips"), "fish n chips")
        self.assertEqual(self.sanitize("london vs. arsenal"), "london vs arsenal")

    def test_collapses_extra_whitespace(self):
        result = self.sanitize("  too   many   spaces  ")
        self.assertNotIn("  ", result)
        self.assertEqual(result, result.strip())

    def test_empty_string_returns_empty(self):
        self.assertEqual(self.sanitize(""), "")

    def test_plain_words_unchanged(self):
        self.assertEqual(self.sanitize("energetic cooking"), "energetic cooking")

    def test_strips_non_ascii_accented_characters(self):
        """Accented letters are transliterated to ASCII equivalents."""
        self.assertEqual(self.sanitize("América toluca"), "America toluca")
        self.assertEqual(self.sanitize("café crème"), "cafe creme")
        self.assertEqual(self.sanitize("sauté onion"), "saute onion")

    def test_non_ascii_only_string_returns_cleaned(self):
        """String made entirely of non-ASCII chars becomes empty or ASCII-safe."""
        result = self.sanitize("日本料理")
        # After stripping non-ASCII, result should contain only ASCII (possibly empty)
        self.assertTrue(result.isascii())


class TestGetMusicForScenesWavCache(unittest.TestCase):
    """Tests that the cache lookup recognises WAV silence-fallback files."""

    def setUp(self):
        import src.music_selector as ms
        self.ms = ms

    def test_returns_cached_wav_file(self):
        """A previously generated WAV silence file is served from cache."""
        fake_wav_path = Path("/tmp/cache/abc123_silence.wav")
        with patch.object(self.ms.config, "MUSIC_ENABLED", True), \
             patch.object(self.ms.config, "MUSIC_CACHE_DIR", "/tmp/test_music_cache"), \
             patch("src.music_selector.Path") as mock_path_cls:
            mock_dir = MagicMock()
            mock_dir.glob.return_value = [fake_wav_path]
            mock_dir.mkdir.return_value = None
            mock_path_cls.return_value = mock_dir
            result = self.ms.get_music_for_scenes(["cooking scene"], "chicken tikka")
        self.assertEqual(result, fake_wav_path)


if __name__ == "__main__":
    unittest.main()
