"""
music_selector.py — Scene-aware background music selection for the Food Making Videos Factory.

Classifies scenes by type (intro / middle / punchline) and downloads royalty-free
background music from free sources using a multi-source fallback chain:

  1. Pixabay Music API — requires ``PIXABAY_API_KEY`` (free registration at pixabay.com).
  2. Free Music Archive API — no API key required; Creative Commons licensed tracks.
  3. Freesound API    — optional; requires ``FREESOUND_API_KEY`` (free registration at
                        freesound.org/apiv2/apply/).
  4. Local silence fallback — generates a short silent WAV file so the pipeline always
                              has an audio track without requiring any API key or network access.

Downloaded tracks are cached locally under ``MUSIC_CACHE_DIR`` to avoid redundant
API calls across pipeline runs.
"""

import hashlib
import logging
import re
import time
import wave
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scene-type → music mood search queries
# ---------------------------------------------------------------------------
_SCENE_MOOD_MAP: dict[str, list[str]] = {
    "intro": [
        "uplifting cooking background music",
        "cheerful kitchen background music",
        "happy food background",
    ],
    "middle": [
        "energetic cooking background music",
        "upbeat kitchen background music",
        "lively food preparation music",
    ],
    "punchline": [
        "triumphant reveal background music",
        "satisfying achievement music",
        "happy celebration food music",
    ],
}

_FREESOUND_SEARCH_URL = "https://freesound.org/apiv2/search/text/"
_PIXABAY_API_URL = "https://pixabay.com/api/"
_FMA_API_URL = "https://freemusicarchive.org/api/get/tracks.json"

# Retry settings for transient API failures (429 Too Many Requests, 503 Service Unavailable)
_FMA_MAX_RETRIES = 3
_FMA_RETRY_STATUSES = frozenset({429, 503})


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _sanitize_topic(topic: str) -> str:
    """Strip characters from *topic* that could break API query strings.

    Replaces any character that is not a word character (letter, digit, or
    underscore) or ASCII space with a single space, then collapses runs of
    whitespace so the result is a clean, human-readable phrase.

    Args:
        topic: Raw topic string from the script generator (may contain
               punctuation, special characters, or Unicode symbols).

    Returns:
        A sanitised version of *topic* suitable for inclusion in a URL
        query parameter.
    """
    sanitized = re.sub(r"[^\w\s]", " ", topic)
    return " ".join(sanitized.split())


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def classify_scene_type(scene_index: int, total_scenes: int) -> str:
    """Return the type of a scene based on its position in the video.

    Args:
        scene_index:   Zero-based index of the scene.
        total_scenes:  Total number of scenes in the video.

    Returns:
        ``'intro'`` for the first scene, ``'punchline'`` for the last,
        and ``'middle'`` for all others.  Returns ``'middle'`` when
        ``total_scenes`` is 1 or less.
    """
    if total_scenes <= 1:
        return "middle"
    if scene_index == 0:
        return "intro"
    if scene_index >= total_scenes - 1:
        return "punchline"
    return "middle"


def get_mood_for_scene(scene_type: str) -> str:
    """Return a music search query string for the given scene type.

    Rotates among available mood phrases hourly for variety.

    Args:
        scene_type: One of ``'intro'``, ``'middle'``, or ``'punchline'``.
                    Falls back to ``'middle'`` if unrecognised.

    Returns:
        A descriptive music search query string.
    """
    import time

    moods = _SCENE_MOOD_MAP.get(scene_type, _SCENE_MOOD_MAP["middle"])
    idx = int(time.time() // 3600) % len(moods)
    return moods[idx]


def get_music_for_scenes(scenes: list[str], topic: str) -> Path | None:
    """Select and download background music suitable for the given video scenes.

    Determines the dominant scene type from the scene list and searches
    multiple free music sources in priority order.  Previously downloaded
    tracks are served from the local cache to minimise API usage.

    Fallback chain (in order):
      1. Pixabay Music API (requires ``PIXABAY_API_KEY``)
      2. Free Music Archive API (no API key required)
      3. Freesound API (requires ``FREESOUND_API_KEY``)
      4. Local silence generator (always succeeds)

    Args:
        scenes: List of scene description strings from script generation.
        topic:  The food topic being covered (used to refine the search).

    Returns:
        Path to the downloaded audio file, or ``None`` if music is
        unavailable (music disabled in config or all fallbacks fail).
    """
    if not getattr(config, "MUSIC_ENABLED", True):
        logger.info("Background music disabled via MUSIC_ENABLED config")
        return None

    cache_dir = Path(getattr(config, "MUSIC_CACHE_DIR", "cache/music"))
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create music cache directory '%s': %s", cache_dir, exc)
        return None

    # Pick a scene type representative of the overall video content
    total = len(scenes)
    primary_scene_type = "intro" if total <= 2 else "middle"
    mood_query = get_mood_for_scene(primary_scene_type)
    # Sanitize the topic to remove characters that could break API query strings,
    # then blend it into the search for more relevant results.
    clean_topic = _sanitize_topic(topic) if topic else ""
    search_query = f"{mood_query} {clean_topic}".strip() if clean_topic else mood_query

    # Check local cache before hitting the API (MP3 downloads and WAV silence fallbacks)
    cache_key = hashlib.md5(search_query.encode()).hexdigest()[:12]
    cached = (
        list(cache_dir.glob(f"{cache_key}_*.mp3"))
        or list(cache_dir.glob(f"{cache_key}_*.wav"))
    )
    if cached:
        logger.info("Using cached background music: %s", cached[0])
        return cached[0]

    # --- Fallback chain (respects MUSIC_SOURCE_PRIORITY order) ---
    source_priority = getattr(config, "MUSIC_SOURCE_PRIORITY",
                              ["pixabay", "free_music_archive", "freesound",
                               "incompetech", "ccmixter", "local_cache", "silence"])

    # Determine primary scene mood for no-API sources
    mood = classify_scene_type(0, len(scenes))

    _source_handlers = {
        "pixabay": lambda: _download_from_pixabay(search_query, cache_dir, cache_key),
        "free_music_archive": lambda: _download_from_free_music_archive(search_query, cache_dir, cache_key),
        "freesound": lambda: _download_from_freesound(search_query, cache_dir, cache_key),
        "incompetech": lambda: _download_from_incompetech(mood, cache_dir, cache_key),
        "ccmixter": lambda: _download_from_ccmixter(mood, cache_dir, cache_key),
        "local_cache": lambda: _get_local_cached_track(cache_dir),
        "silence": lambda: _create_silence_fallback(cache_dir, cache_key),
    }

    for source in source_priority:
        handler = _source_handlers.get(source)
        if handler is None:
            logger.warning("Unknown music source '%s' in MUSIC_SOURCE_PRIORITY — skipping", source)
            continue
        result = handler()
        if result:
            if source == "silence":
                logger.info("Using silence fallback — no API music available")
            return result

    logger.warning("No background music sourced — video will use TTS narration only")
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _download_from_pixabay(query: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Search Pixabay for background music and download the best match.

    Requires ``PIXABAY_API_KEY`` to be set in the environment.
    Queries Pixabay's audio endpoint and downloads the first available track.

    Args:
        query:     Search query string.
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on any failure.
    """
    api_key = getattr(config, "PIXABAY_API_KEY", None)
    if not api_key:
        logger.debug("PIXABAY_API_KEY not configured — skipping Pixabay music search")
        return None

    try:
        resp = requests.get(
            _PIXABAY_API_URL,
            params={
                "key": api_key,
                "q": query,
                "media_type": "music",
                "per_page": 5,
            },
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

        if not hits:
            logger.debug("Pixabay returned no music results for query '%s'", query)
            return None

        for hit in hits:
            audio_url = hit.get("audio")
            if not audio_url or not audio_url.endswith(".mp3"):
                continue

            track_id = hit.get("id", "unknown")
            out_path = cache_dir / f"{cache_key}_pixabay_{track_id}.mp3"

            try:
                with requests.get(audio_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            fh.write(chunk)
                logger.info(
                    "Downloaded Pixabay background music (id=%s) → %s", track_id, out_path
                )
                return out_path
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to download Pixabay track id=%s: %s", track_id, exc)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Pixabay music search failed for query '%s': %s", query, exc)

    return None


def _download_from_free_music_archive(query: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Search the Free Music Archive for Creative Commons background music.

    No API key is required.  Downloads the first available track whose
    download URL is exposed by the API.

    The query is percent-encoded (using ``%20`` for spaces rather than ``+``)
    to avoid 404 errors from the FMA API.  Transient server errors (HTTP 429
    and 503) are retried with exponential backoff up to ``_FMA_MAX_RETRIES``
    times before giving up.

    Args:
        query:     Search query string (will be sanitised and URL-encoded).
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on any failure.
    """
    # Build the request URL with explicit percent-encoding (%20 for spaces)
    # so that the FMA API receives a well-formed query string.
    params_str = urlencode(
        {"q": query, "limit": 5, "sort": "track_date_published", "order": "desc"},
        quote_via=quote,
    )
    request_url = f"{_FMA_API_URL}?{params_str}"

    for attempt in range(_FMA_MAX_RETRIES):
        try:
            resp = requests.get(request_url, timeout=15)
            resp.raise_for_status()
            tracks = resp.json().get("aTracks", [])

            if not tracks:
                logger.debug("Free Music Archive returned no results for query '%s'", query)
                return None

            for track in tracks:
                download_url = track.get("track_file") or track.get("track_url")
                if not download_url:
                    continue

                track_id = track.get("track_id", "unknown")
                out_path = cache_dir / f"{cache_key}_fma_{track_id}.mp3"

                try:
                    with requests.get(download_url, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        with open(out_path, "wb") as fh:
                            for chunk in r.iter_content(chunk_size=8192):
                                fh.write(chunk)
                    logger.info(
                        "Downloaded Free Music Archive track '%s' (id=%s) → %s",
                        track.get("track_title", track_id), track_id, out_path,
                    )
                    return out_path
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to download FMA track id=%s: %s", track_id, exc)

            return None

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if exc.response is not None and exc.response.status_code in _FMA_RETRY_STATUSES:
                wait = 2 ** attempt
                logger.warning(
                    "Free Music Archive transient error (HTTP %s) for query '%s' — "
                    "retrying in %ds (attempt %d/%d)",
                    status, query, wait, attempt + 1, _FMA_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            logger.warning(
                "Free Music Archive search failed for query '%s': HTTP %s — %s",
                query, status, exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Free Music Archive search failed for query '%s': %s", query, exc)
            return None

    logger.warning(
        "Free Music Archive search gave up after %d retries for query '%s'",
        _FMA_MAX_RETRIES, query,
    )
    return None


def _download_from_freesound(query: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Search Freesound for background music and download the best match.

    Requires ``FREESOUND_API_KEY`` to be set in the environment.
    Downloads the high-quality MP3 preview of the top-rated result.

    Args:
        query:     Search query string.
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on any failure.
    """
    api_key = getattr(config, "FREESOUND_API_KEY", None)
    if not api_key:
        logger.debug("FREESOUND_API_KEY not configured — skipping Freesound music search")
        return None

    try:
        resp = requests.get(
            _FREESOUND_SEARCH_URL,
            params={
                "query": query,
                "filter": "duration:[30 TO 180] type:mp3",
                "fields": "id,name,previews,duration,license",
                "sort": "rating_desc",
                "page_size": 5,
                "token": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            logger.debug("Freesound returned no results for query '%s'", query)
            return None

        # Pick the first result that exposes a downloadable preview URL
        for result in results:
            previews = result.get("previews", {})
            preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
            if not preview_url:
                continue

            sound_id = result.get("id", "unknown")
            out_path = cache_dir / f"{cache_key}_{sound_id}.mp3"

            try:
                with requests.get(preview_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            fh.write(chunk)
                logger.info(
                    "Downloaded background music '%s' (id=%s) → %s",
                    result.get("name", sound_id), sound_id, out_path,
                )
                return out_path
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to download Freesound preview for id=%s: %s", sound_id, exc
                )

    except Exception as exc:  # noqa: BLE001
        logger.warning("Freesound search failed for query '%s': %s", query, exc)

    return None


def _create_silence_fallback(cache_dir: Path, cache_key: str) -> Path | None:
    """Generate a short silent WAV file as a last-resort music fallback.

    Uses only Python's standard-library ``wave`` module — no external
    dependencies or network access required.  Produces a 60-second mono
    16-bit PCM WAV at 22 050 Hz (≈ 2.6 MB) which is long enough for any
    YouTube Short.  The file is reused on subsequent pipeline runs.

    Args:
        cache_dir: Directory where the silence file will be written.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the generated WAV file, or ``None`` if writing fails.
    """
    out_path = cache_dir / f"{cache_key}_silence.wav"
    if out_path.exists():
        logger.debug("Reusing existing silence fallback: %s", out_path)
        return out_path

    sample_rate = 22050   # Hz — low sample rate keeps the file small
    num_channels = 1      # mono
    sample_width = 2      # 16-bit PCM
    duration_s = 60       # seconds

    try:
        # Write one second of silence at a time to avoid a large in-memory allocation
        silence_chunk = b"\x00" * sample_rate * num_channels * sample_width
        with wave.open(str(out_path), "w") as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            for _ in range(duration_s):
                wf.writeframes(silence_chunk)
        logger.info("Created silence fallback audio (%ds WAV): %s", duration_s, out_path)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create silence fallback audio: %s", exc)
        return None


def _download_from_incompetech(mood: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Download a royalty-free CC BY track from Incompetech (no API key required).

    Delegates to :func:`src.music_alternatives.download_incompetech`.

    Args:
        mood:      Scene mood — ``'intro'``, ``'middle'``, or ``'punchline'``.
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on failure.
    """
    try:
        from src.music_alternatives import download_incompetech  # noqa: PLC0415
        return download_incompetech(mood, cache_dir, cache_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Incompetech music source failed: %s", exc)
        return None


def _download_from_ccmixter(mood: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Download a Creative Commons track from ccMixter (no API key required).

    Delegates to :func:`src.music_alternatives.download_ccmixter`.

    Args:
        mood:      Scene mood string.
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on failure.
    """
    try:
        from src.music_alternatives import download_ccmixter  # noqa: PLC0415
        return download_ccmixter(mood, cache_dir, cache_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ccMixter music source failed: %s", exc)
        return None


def _get_local_cached_track(cache_dir: Path) -> Path | None:
    """Return a random previously-downloaded track from the local music cache.

    Delegates to :func:`src.music_alternatives.get_local_cached_track`.
    Provides a purely offline fallback that never makes network requests.

    Args:
        cache_dir: Directory to scan for audio files.

    Returns:
        Path to a randomly chosen ``*.mp3`` / ``*.wav`` file, or ``None``.
    """
    try:
        from src.music_alternatives import get_local_cached_track  # noqa: PLC0415
        return get_local_cached_track(cache_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Local cache music source failed: %s", exc)
        return None
