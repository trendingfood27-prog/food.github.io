"""
footage_alternatives.py — Additional stock footage and video fallback sources
for the Food Making Videos Factory.

Provides multiple free/open video sources beyond the primary Pexels integration:

  1. Coverr.co   — free stock video library, no API key required.
  2. Videvo.net  — free stock footage, no API key for basic search.
  3. YouTube Creative Commons search — CC-licensed clips via YouTube Data API.
  4. AI-generated placeholder clip — a simple colour-gradient clip created
                                     with MoviePy when no network source works.
  5. Ken Burns effect on images — animates a still image to create a
                                   pseudo-video when no actual footage is found.

Each function returns a ``Path`` to a local ``.mp4`` file on success, or
``None`` on failure, so they can be integrated into ``video_creator.py``'s
footage-fetch loop without changing its contract.
"""

import logging
import math
import random
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coverr.co — free stock videos, no API key required
# ---------------------------------------------------------------------------
_COVERR_API_URL = "https://api.coverr.co/videos"

_COVERR_FOOD_QUERIES: list[str] = [
    "cooking",
    "food",
    "kitchen",
    "recipe",
    "chef",
    "baking",
    "vegetables",
    "pasta",
    "grilling",
    "fresh ingredients",
]


def search_coverr(query: str, per_page: int = 5) -> list[str]:
    """Search Coverr.co for free stock food videos.

    Args:
        query:    Search term (e.g. ``'cooking pasta'``).
        per_page: Maximum number of results to return.

    Returns:
        List of direct MP4 download URLs (may be empty on failure).
    """
    try:
        resp = requests.get(
            _COVERR_API_URL,
            params={
                "keywords": query,
                "page": 1,
                "per_page": per_page,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        urls: list[str] = []
        for item in data.get("hits", []):
            # Prefer the 1080p MP4; fall back to any available resolution
            sources = item.get("sources", {})
            url = (
                sources.get("mp4_url")
                or sources.get("hd")
                or sources.get("sd")
            )
            if url:
                urls.append(url)
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.debug("Coverr search failed for query '%s': %s", query, exc)
        return []


def fetch_coverr_clip(scene_description: str, download_dir: Path) -> Path | None:
    """Download a Coverr.co video clip matching *scene_description*.

    Falls back to a generic food-keyword search if the specific scene query
    returns no results.

    Args:
        scene_description: Textual description of the desired footage.
        download_dir:      Directory to save the downloaded clip.

    Returns:
        Path to the downloaded MP4, or ``None`` on failure.
    """
    download_dir.mkdir(parents=True, exist_ok=True)

    # Try the scene description directly, then fall back to generic food terms
    queries_to_try = [scene_description] + random.sample(
        _COVERR_FOOD_QUERIES,
        min(3, len(_COVERR_FOOD_QUERIES)),
    )

    for query in queries_to_try:
        urls = search_coverr(query, per_page=5)
        for url in urls:
            fname = f"coverr_{abs(hash(url)) % 10**8}.mp4"
            out_path = download_dir / fname
            if out_path.exists():
                return out_path
            try:
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            fh.write(chunk)
                logger.info("Downloaded Coverr clip → %s", out_path)
                return out_path
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to download Coverr clip from %s: %s", url, exc)
                out_path.unlink(missing_ok=True)

    logger.debug("No Coverr clips found for scene: '%s'", scene_description)
    return None


# ---------------------------------------------------------------------------
# Videvo.net — free stock footage, no API key needed for the public endpoint
# ---------------------------------------------------------------------------
_VIDEVO_SEARCH_URL = "https://www.videvo.net/api/v1/footage"


def search_videvo(query: str, per_page: int = 5) -> list[str]:
    """Search Videvo for free stock footage.

    Args:
        query:    Search term.
        per_page: Maximum results to request.

    Returns:
        List of direct MP4 download URLs (may be empty on failure).
    """
    try:
        resp = requests.get(
            _VIDEVO_SEARCH_URL,
            params={
                "search_query": query,
                "page": 1,
                "per_page": per_page,
                "type": "footage",
                "license_type": "free",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        urls: list[str] = []
        for item in data.get("results", []):
            url = item.get("file_url") or item.get("preview_url")
            if url and url.endswith(".mp4"):
                urls.append(url)
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.debug("Videvo search failed for query '%s': %s", query, exc)
        return []


def fetch_videvo_clip(scene_description: str, download_dir: Path) -> Path | None:
    """Download a Videvo stock clip matching *scene_description*.

    Args:
        scene_description: Scene description used as the search query.
        download_dir:      Directory to save the downloaded clip.

    Returns:
        Path to the downloaded MP4, or ``None`` on failure.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    for url in search_videvo(scene_description, per_page=5):
        fname = f"videvo_{abs(hash(url)) % 10**8}.mp4"
        out_path = download_dir / fname
        if out_path.exists():
            return out_path
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        fh.write(chunk)
            logger.info("Downloaded Videvo clip → %s", out_path)
            return out_path
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to download Videvo clip: %s", exc)
            out_path.unlink(missing_ok=True)
    return None


# ---------------------------------------------------------------------------
# YouTube Creative Commons search via YouTube Data API v3
# ---------------------------------------------------------------------------

def search_youtube_cc(query: str, api_key: str | None = None) -> list[str]:
    """Return YouTube video IDs for Creative Commons licensed clips.

    Requires a YouTube Data API v3 key (``YOUTUBE_DATA_API_KEY`` in config
    or the *api_key* argument).  Returns an empty list when no key is available
    so callers can silently skip this source.

    Args:
        query:   Search phrase.
        api_key: Optional override for the YouTube Data API key.

    Returns:
        List of YouTube video IDs (may be empty).
    """
    key = api_key or getattr(config, "YOUTUBE_DATA_API_KEY", None)
    if not key:
        logger.debug("YOUTUBE_DATA_API_KEY not configured — skipping YouTube CC search")
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "id",
                "q": query,
                "type": "video",
                "videoLicense": "creativeCommon",
                "maxResults": 5,
                "key": key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            item["id"]["videoId"]
            for item in resp.json().get("items", [])
            if item.get("id", {}).get("videoId")
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("YouTube CC search failed for '%s': %s", query, exc)
        return []


# ---------------------------------------------------------------------------
# AI-generated placeholder clip using MoviePy
# ---------------------------------------------------------------------------
# Creates a simple gradient colour animation so the pipeline never has
# completely black footage when all remote sources fail.

_FOOD_COLORS: list[tuple[int, int, int]] = [
    (255, 140, 0),   # deep orange
    (220, 90, 30),   # burnt orange
    (180, 50, 20),   # dark red
    (255, 200, 50),  # golden yellow
    (80, 160, 40),   # fresh green
    (200, 80, 20),   # paprika red
]


def create_placeholder_clip(
    duration: float,
    width: int,
    height: int,
    scene_index: int = 0,
) -> Path | None:
    """Generate a simple animated colour-gradient placeholder clip with MoviePy.

    Used as a last-resort fallback when no actual stock footage can be
    obtained.  Creates a warm food-themed gradient that pans vertically to
    simulate motion.

    Args:
        duration:    Clip duration in seconds.
        width:       Frame width in pixels.
        height:      Frame height in pixels.
        scene_index: Scene index (controls colour selection for variety).

    Returns:
        Path to the generated MP4 file, or ``None`` if MoviePy is unavailable.
    """
    try:
        from moviepy.editor import ColorClip, VideoClip  # type: ignore[import]
        import numpy as np
    except ImportError:
        logger.debug("MoviePy or NumPy not available — cannot create placeholder clip")
        return None

    color = _FOOD_COLORS[scene_index % len(_FOOD_COLORS)]
    # Blend from the chosen colour to a slightly warmer version over the clip
    r, g, b = color
    end_r = min(255, r + 30)
    end_g = max(0, g - 20)
    end_b = max(0, b - 10)

    def make_frame(t: float) -> Any:
        progress = t / max(duration, 0.001)
        cr = int(r + (end_r - r) * progress)
        cg = int(g + (end_g - g) * progress)
        cb = int(b + (end_b - b) * progress)
        # Create a gradient from top to bottom with slight vertical pan
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            blend = y / height
            frame[y, :, 0] = int(cr * (1 - blend * 0.4))
            frame[y, :, 1] = int(cg * (1 - blend * 0.3))
            frame[y, :, 2] = int(cb * (1 - blend * 0.2))
        return frame

    try:
        clip = VideoClip(make_frame, duration=duration)
        out_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = Path(out_file.name)
        out_file.close()
        clip.write_videofile(
            str(out_path),
            fps=24,
            codec="libx264",
            audio=False,
            logger=None,
        )
        clip.close()
        logger.info("Created AI placeholder clip (scene %d, %.1fs) → %s", scene_index, duration, out_path)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to create placeholder clip: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Ken Burns effect — animates a still image into a pseudo-video clip
# ---------------------------------------------------------------------------

def apply_ken_burns(
    image_path: Path,
    duration: float,
    width: int,
    height: int,
) -> Path | None:
    """Apply a Ken Burns pan-and-zoom effect to an image, producing a short video.

    The effect slowly zooms in from 100% to 120% while panning from the
    centre toward a corner.  This is a common technique to add motion to
    still food photography.

    Args:
        image_path: Path to the source image (any PIL-supported format).
        duration:   Desired clip duration in seconds.
        width:      Output frame width.
        height:     Output frame height.

    Returns:
        Path to the generated MP4 file, or ``None`` on failure.
    """
    try:
        from moviepy.editor import ImageClip  # type: ignore[import]
        from PIL import Image  # type: ignore[import]
        import numpy as np
    except ImportError:
        logger.debug("MoviePy / Pillow not available — cannot apply Ken Burns effect")
        return None

    try:
        img = Image.open(image_path).convert("RGB")
        img_w, img_h = img.size
        # Upscale the source image so there is room to pan and zoom
        scale = 1.4
        large_w = int(img_w * scale)
        large_h = int(img_h * scale)
        img_large = img.resize((large_w, large_h), Image.LANCZOS)
        img_array = np.array(img_large)

        def make_frame(t: float) -> Any:
            progress = t / max(duration, 0.001)
            zoom = 1.0 + 0.2 * progress  # 1.0× → 1.2× zoom
            crop_w = int(width / zoom)
            crop_h = int(height / zoom)
            max_x = large_w - crop_w
            max_y = large_h - crop_h
            x0 = int(max_x * 0.5 * (1 - progress))
            y0 = int(max_y * 0.5 * progress)
            x0 = max(0, min(x0, large_w - crop_w))
            y0 = max(0, min(y0, large_h - crop_h))
            cropped = img_array[y0: y0 + crop_h, x0: x0 + crop_w]
            # Resize crop back to output dimensions
            pil_crop = Image.fromarray(cropped).resize((width, height), Image.LANCZOS)
            return np.array(pil_crop)

        from moviepy.editor import VideoClip  # type: ignore[import]

        clip = VideoClip(make_frame, duration=duration)
        out_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = Path(out_file.name)
        out_file.close()
        clip.write_videofile(
            str(out_path),
            fps=24,
            codec="libx264",
            audio=False,
            logger=None,
        )
        clip.close()
        logger.info("Applied Ken Burns effect to '%s' → %s", image_path.name, out_path)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ken Burns effect failed for '%s': %s", image_path, exc)
        return None


# ---------------------------------------------------------------------------
# Unified fallback fetcher
# ---------------------------------------------------------------------------

def fetch_fallback_clip(
    scene_description: str,
    duration: float,
    width: int,
    height: int,
    scene_index: int = 0,
    download_dir: Path | None = None,
) -> Path | None:
    """Attempt to obtain a video clip from any available alternative source.

    Tries in order:
      1. Coverr.co
      2. Videvo.net
      3. AI-generated colour-gradient placeholder

    Args:
        scene_description: Text description of the desired footage.
        duration:          Desired clip duration in seconds.
        width:             Frame width for placeholder generation.
        height:            Frame height for placeholder generation.
        scene_index:       Scene index for placeholder colour selection.
        download_dir:      Directory for downloaded files. Defaults to a
                           system temp directory.

    Returns:
        Path to a video clip, or ``None`` if all sources fail.
    """
    if download_dir is None:
        download_dir = Path(tempfile.mkdtemp(prefix="footage_alt_"))

    for name, fn in [
        ("Coverr", lambda: fetch_coverr_clip(scene_description, download_dir)),
        ("Videvo", lambda: fetch_videvo_clip(scene_description, download_dir)),
    ]:
        result = fn()
        if result:
            return result
        logger.debug("Footage source '%s' returned nothing — trying next", name)

    # Final fallback: AI-generated placeholder
    return create_placeholder_clip(duration, width, height, scene_index)
