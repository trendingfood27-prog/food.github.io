"""
music_alternatives.py — No-API and low-API background music sources for the
Food Making Videos Factory.

Provides additional free music sources that require **no API key**:

  1. Incompetech (Kevin MacLeod) — large CC BY licensed catalogue, no key needed.
  2. ccMixter   — Creative Commons music community, no key needed.
  3. Musopen    — Classical / public-domain music, no key needed.
  4. Local offline rotation — cycles through any ``*.mp3`` / ``*.wav`` files
                               already present in ``MUSIC_CACHE_DIR``.

All downloaders return a ``Path`` on success or ``None`` on failure so they
can be dropped straight into the ``music_selector`` fallback chain.
"""

import hashlib
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Incompetech (Kevin MacLeod) — free CC BY music, no API key required
# ---------------------------------------------------------------------------
# Incompetech does not expose a formal JSON API, but a small set of
# hand-curated direct MP3 download links covers the most useful moods.
# These are all CC BY 4.0 licensed (attribution: Kevin MacLeod, incompetech.com).
_INCOMPETECH_TRACKS: dict[str, list[dict]] = {
    "cooking": [
        {
            "id": "fluffing_a_duck",
            "title": "Fluffing a Duck",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fluffing%20a%20Duck.mp3",
        },
        {
            "id": "sneaky_snitch",
            "title": "Sneaky Snitch",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3",
        },
        {
            "id": "call_to_adventure",
            "title": "Call to Adventure",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Call%20to%20Adventure.mp3",
        },
    ],
    "upbeat": [
        {
            "id": "happy_bee",
            "title": "Happy Bee",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Happy%20Bee.mp3",
        },
        {
            "id": "better_days",
            "title": "Better Days",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Better%20Days.mp3",
        },
        {
            "id": "funkorama",
            "title": "Funkorama",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Funkorama.mp3",
        },
    ],
    "relaxed": [
        {
            "id": "acoustic_breeze",
            "title": "Acoustic Breeze",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Acoustic%20Breeze.mp3",
        },
        {
            "id": "going_higher",
            "title": "Going Higher",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Going%20Higher.mp3",
        },
    ],
    "reveal": [
        {
            "id": "local_forecast",
            "title": "Local Forecast - Elevator",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Local%20Forecast%20-%20Elevator.mp3",
        },
        {
            "id": "sunshine",
            "title": "Sunshine",
            "url": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sunshine.mp3",
        },
    ],
}

# Mood → track-list key mapping so callers can pass free-form mood strings
_MOOD_ALIAS: dict[str, str] = {
    "intro": "cooking",
    "middle": "upbeat",
    "punchline": "reveal",
    "cooking": "cooking",
    "upbeat": "upbeat",
    "relaxed": "relaxed",
    "reveal": "reveal",
}


def download_incompetech(mood: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Download a royalty-free track from Incompetech (Kevin MacLeod).

    No API key is required.  Selects from a hand-curated list of CC BY 4.0
    licensed tracks matching the given *mood* and downloads it to *cache_dir*.
    Starts from a track determined by the current hour for variety, then
    falls through the remaining tracks in the list if the first choice fails.

    Args:
        mood:      Scene mood — one of ``'intro'``, ``'middle'``, ``'punchline'``,
                   ``'cooking'``, ``'upbeat'``, ``'relaxed'``, or ``'reveal'``.
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on failure.
    """
    bucket_key = _MOOD_ALIAS.get(mood, "upbeat")
    tracks = _INCOMPETECH_TRACKS.get(bucket_key, _INCOMPETECH_TRACKS["upbeat"])

    # Rotate hourly for variety, but fall through all tracks on failure
    start_idx = int(time.time() // 3600) % len(tracks)
    ordered = tracks[start_idx:] + tracks[:start_idx]

    for track in ordered:
        out_path = cache_dir / f"{cache_key}_incompetech_{track['id']}.mp3"
        if out_path.exists():
            logger.info("Reusing cached Incompetech track '%s': %s", track["title"], out_path)
            return out_path

        try:
            with requests.get(track["url"], stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(out_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        fh.write(chunk)
            logger.info(
                "Downloaded Incompetech track '%s' (CC BY Kevin MacLeod) → %s",
                track["title"],
                out_path,
            )
            return out_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to download Incompetech track '%s': %s", track["title"], exc)
            if out_path.exists():
                out_path.unlink(missing_ok=True)

    return None


# ---------------------------------------------------------------------------
# ccMixter — Creative Commons community music, no API key required
# ---------------------------------------------------------------------------
_CCMIXTER_API_URL = "http://ccmixter.org/api/query"

_CCMIXTER_FOOD_QUERIES = [
    "upbeat cooking",
    "cheerful kitchen",
    "happy food",
    "energetic background",
    "positive vibes",
]


def download_ccmixter(mood: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Search ccMixter for a Creative Commons track and download it.

    ccMixter exposes a public query API with no authentication.  Results
    are filtered to tracks that expose an MP3 download URL.

    Args:
        mood:      Scene mood string (used to pick search query).
        cache_dir: Directory to save the downloaded file.
        cache_key: Short hash used as part of the cached filename.

    Returns:
        Path to the downloaded MP3, or ``None`` on failure.
    """
    # Pick a query that matches the mood
    mood_lower = mood.lower()
    if "intro" in mood_lower or "cooking" in mood_lower:
        query = "upbeat cooking"
    elif "reveal" in mood_lower or "punchline" in mood_lower:
        query = "happy positive reveal"
    else:
        # Rotate queries hourly for variety
        idx = int(time.time() // 3600) % len(_CCMIXTER_FOOD_QUERIES)
        query = _CCMIXTER_FOOD_QUERIES[idx]

    try:
        resp = requests.get(
            _CCMIXTER_API_URL,
            params={
                "tags": query,
                "type": "cchost",
                "format": "json",
                "limit": 10,
                "sort": "rank",
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            logger.debug("ccMixter returned no results for query '%s'", query)
            return None

        random.shuffle(results)
        for item in results:
            files = item.get("files", [])
            mp3_url: str | None = None
            for f in files:
                media_url = f.get("download_url") or f.get("file_url", "")
                if media_url.endswith(".mp3"):
                    mp3_url = media_url
                    break
            if not mp3_url:
                continue

            # Normalise to HTTP to avoid SSL certificate verification failures
            # that can occur with the ccmixter.org HTTPS endpoint in some
            # environments (e.g. CI runners without updated CA bundles).
            parsed = urlparse(mp3_url)
            if parsed.scheme == "https" and parsed.netloc == "ccmixter.org":
                mp3_url = urlunparse(parsed._replace(scheme="http"))

            upload_id = item.get("upload_id", "unknown")
            out_path = cache_dir / f"{cache_key}_ccmixter_{upload_id}.mp3"

            try:
                with requests.get(mp3_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            fh.write(chunk)
                logger.info(
                    "Downloaded ccMixter track '%s' (id=%s) → %s",
                    item.get("upload_name", upload_id),
                    upload_id,
                    out_path,
                )
                return out_path
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to download ccMixter track id=%s: %s", upload_id, exc)

    except Exception as exc:  # noqa: BLE001
        logger.warning("ccMixter search failed for query '%s': %s", query, exc)

    return None


# ---------------------------------------------------------------------------
# Local offline rotation — reuse any cached track already on disk
# ---------------------------------------------------------------------------

def get_local_cached_track(cache_dir: Path) -> Path | None:
    """Return a randomly selected music file already present in *cache_dir*.

    This is a pure offline fallback — it never makes a network request and
    is guaranteed to succeed as long as at least one audio file exists in the
    cache directory.

    Args:
        cache_dir: Directory to scan for audio files.

    Returns:
        Path to a randomly chosen ``*.mp3`` or ``*.wav`` file, or ``None``
        if the cache directory is empty or does not exist.
    """
    if not cache_dir.exists():
        logger.debug("Music cache directory '%s' does not exist — no local tracks", cache_dir)
        return None

    candidates = list(cache_dir.glob("*.mp3")) + list(cache_dir.glob("*.wav"))
    # Exclude the silence placeholder so the pipeline actually gets music
    candidates = [
        p for p in candidates
        if "silence" not in p.stem.lower()
    ]

    if not candidates:
        logger.debug("No usable cached music tracks found in '%s'", cache_dir)
        return None

    chosen = random.choice(candidates)
    logger.info("Using locally cached music track (offline rotation): %s", chosen)
    return chosen


# ---------------------------------------------------------------------------
# Convenience wrapper — try all no-API sources in sequence
# ---------------------------------------------------------------------------

def download_no_api_music(mood: str, cache_dir: Path, cache_key: str) -> Path | None:
    """Attempt to download background music without requiring any API key.

    Tries sources in order:
      1. Incompetech (Kevin MacLeod — CC BY)
      2. ccMixter (CC licensed community music)
      3. Local offline rotation (already-cached tracks)

    Args:
        mood:      Scene mood string passed to individual downloaders.
        cache_dir: Local cache directory.
        cache_key: Short hash for unique filenames.

    Returns:
        Path to an audio file on success, or ``None`` if all sources fail.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    for name, fn in [
        ("Incompetech", lambda: download_incompetech(mood, cache_dir, cache_key)),
        ("ccMixter", lambda: download_ccmixter(mood, cache_dir, cache_key)),
        ("local cache", lambda: get_local_cached_track(cache_dir)),
    ]:
        result = fn()
        if result:
            return result
        logger.debug("No-API music source '%s' returned nothing — trying next", name)

    return None
