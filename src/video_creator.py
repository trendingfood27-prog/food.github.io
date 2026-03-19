"""
video_creator.py — Build a vertical YouTube Shorts video for the Food Making Videos Factory.

Assembles food footage from multiple stock media sources (Pexels, Pixabay, Unsplash),
TTS audio, and bold captions using MoviePy.

Workflow:
1. Fetch food-themed stock video clips from rotating stock sources (Pexels, Pixabay) for each scene.
2. Use Unsplash as fallback for high-quality food photography with Ken Burns effect.
3. Resize / crop each clip to 1080 × 1920 (portrait).
4. Apply warm, vibrant colour grading for food appeal.
5. Concatenate clips with crossfade transitions.
6. Overlay TTS audio with optional background music.
7. Burn bold, engaging captions with warm pill backgrounds.
8. Apply fade-in / fade-out.
9. Export as high-quality H.264/AAC MP4.
"""

import logging
import math
import os
import random
import tempfile
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Pillow 10+ compatibility shims for MoviePy 1.x
# ---------------------------------------------------------------------------
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

for _constant_name in ("FLIP_LEFT_RIGHT", "FLIP_TOP_BOTTOM", "ROTATE_90",
                        "ROTATE_180", "ROTATE_270", "TRANSPOSE", "TRANSVERSE"):
    if not hasattr(Image, _constant_name) and hasattr(Image.Transpose, _constant_name):
        setattr(Image, _constant_name, getattr(Image.Transpose, _constant_name))

import config

logger = logging.getLogger(__name__)

_PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"
_PEXELS_IMAGE_SEARCH = "https://api.pexels.com/v1/search"
_PIXABAY_VIDEO_SEARCH = "https://pixabay.com/api/videos/"
_PIXABAY_IMAGE_SEARCH = "https://pixabay.com/api/"
_UNSPLASH_SEARCH = "https://api.unsplash.com/search/photos"

# ---------------------------------------------------------------------------
# Food-themed search query suffixes — appended to scene descriptions to prefer
# close-up food photography, cooking action shots, and kitchen environments.
# ---------------------------------------------------------------------------
_FOOD_QUERY_SUFFIXES = ["food", "cooking", "recipe", "kitchen", "chef"]
_FOOD_FALLBACK_QUERIES = [
    "food cooking close up",
    "chef cooking kitchen",
    "fresh ingredients recipe",
    "delicious food preparation",
    "cooking pan sizzle",
    "food plating presentation",
    "kitchen cooking tutorial",
    "fresh vegetables cutting",
    "meat grilling cooking",
    "baking bread oven",
]


def _fit_bg_audio_to_duration(bg_audio: Any, target_duration: float, afx: Any) -> Any:
    """Return background audio safely fitted to target duration.

    ``AudioFileClip.set_duration`` can cause out-of-range reads when the clip
    is shorter than the requested duration. Loop short clips and trim long ones
    to keep frame access in-bounds during render.
    """
    if target_duration <= 0:
        return bg_audio

    clip_duration = getattr(bg_audio, "duration", 0.0) or 0.0
    if clip_duration <= 0:
        return bg_audio.set_duration(target_duration)
    if clip_duration < target_duration:
        return bg_audio.fx(afx.audio_loop, duration=target_duration)
    if clip_duration > target_duration:
        return bg_audio.subclip(0, target_duration)
    return bg_audio


def _resolve_target_duration(
    requested_audio_duration: float,
    default_duration: float,
    measured_tts_duration: float | None,
) -> float:
    """Resolve final video duration so narration is never cut short."""
    resolved = requested_audio_duration if requested_audio_duration > 0 else default_duration
    if measured_tts_duration and measured_tts_duration > 0:
        resolved = max(resolved, measured_tts_duration)
    return resolved


def _fit_base_video_duration(base: Any, target_duration: float, vfx: Any) -> Any:
    """Ensure visual timeline fully covers narration duration."""
    if base.duration < target_duration:
        freeze_duration = target_duration - base.duration
        return base.fx(vfx.freeze, t=max(base.duration - 0.05, 0), freeze_duration=freeze_duration)
    if base.duration > target_duration:
        return base.subclip(0, target_duration)
    return base


def _pexels_headers() -> dict[str, str]:
    """Return the Pexels API authorisation header."""
    if not config.PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY environment variable is not set")
    return {"Authorization": config.PEXELS_API_KEY}


def _make_food_query(scene: str) -> str:
    """Build a food-themed search query from a scene description.

    Appends a rotation of food-friendly suffix keywords so returned
    footage shows cooking, ingredients, and food preparation.
    The suffix rotates hourly for variety across runs.
    """
    suffix = _FOOD_QUERY_SUFFIXES[int(math.floor(
        (len(scene) + int(__import__("time").time()) // 3600) % len(_FOOD_QUERY_SUFFIXES)
    ))]
    # Strip scene descriptions to a short, searchable phrase
    words = scene.split()[:6]
    short_scene = " ".join(words)
    return f"{short_scene} {suffix}"


def _search_pexels_video(query: str, per_page: int = 5) -> list[str]:
    """Return a list of downloadable video URLs from Pexels for *query*.

    Tries the food-themed query first; if fewer than 2 results come
    back, falls back to a broader food fallback query.  Prefers the
    highest-resolution HD file for each video result.
    """
    per_page = getattr(config, "PEXELS_PER_PAGE", per_page)

    def _fetch(q: str) -> list[str]:
        try:
            resp = requests.get(
                _PEXELS_VIDEO_SEARCH,
                headers=_pexels_headers(),
                params={"query": q, "per_page": per_page, "orientation": "portrait", "size": "large"},
                timeout=15,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            urls: list[str] = []
            for video in data.get("videos", []):
                files = video.get("video_files", [])
                if not files:
                    continue
                hd_files = sorted(
                    [f for f in files if f.get("quality") == "hd"],
                    key=lambda f: f.get("width", 0) * f.get("height", 0),
                    reverse=True,
                )
                sd_files = sorted(
                    [f for f in files if f.get("quality") == "sd"],
                    key=lambda f: f.get("width", 0) * f.get("height", 0),
                    reverse=True,
                )
                chosen = hd_files[0] if hd_files else sd_files[0] if sd_files else files[0]
                if chosen and chosen.get("link"):
                    urls.append(chosen["link"])
            return urls
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pexels video search failed for '%s': %s", q, exc)
            return []

    # Try the food query first
    food_query = _make_food_query(query)
    urls = _fetch(food_query)

    # If insufficient results, try Pixabay as secondary source
    if len(urls) < 2:
        pixabay_urls = _search_pixabay_video(food_query, per_page=3)
        if pixabay_urls:
            logger.info("Using Pixabay as secondary source for '%s'", food_query)
            urls = pixabay_urls + urls

    # If still insufficient, try a broader food fallback
    if len(urls) < 2:
        fallback_q = random.choice(_FOOD_FALLBACK_QUERIES)
        logger.info("Broadening search from '%s' to '%s'", food_query, fallback_q)
        urls = _fetch(fallback_q) or urls

    return urls


def _search_pixabay_video(query: str, per_page: int = 5) -> list[str]:
    """Search Pixabay for food-related portrait videos matching *query*.

    Requires ``PIXABAY_API_KEY`` to be set; returns empty list gracefully
    if the key is absent or the request fails.
    """
    api_key = getattr(config, "PIXABAY_API_KEY", None)
    if not api_key:
        return []
    try:
        resp = requests.get(
            _PIXABAY_VIDEO_SEARCH,
            params={
                "key": api_key,
                "q": query,
                "video_type": "film",
                "per_page": per_page,
                "safesearch": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        urls: list[str] = []
        for hit in data.get("hits", []):
            videos = hit.get("videos", {})
            for quality in ("medium", "small", "large", "tiny"):
                video_data = videos.get(quality, {})
                url = video_data.get("url")
                if url:
                    urls.append(url)
                    break
        logger.debug("Pixabay video search for '%s': %d results", query, len(urls))
        return urls
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pixabay video search failed for '%s': %s", query, exc)
        return []


def _search_pexels_image(query: str) -> str | None:
    """Return the URL of a portrait photo from Pexels for *query*.

    Prefers food-vibrant imagery by appending "food" to the query.
    """
    try:
        food_query = f"{query} food"
        resp = requests.get(
            _PEXELS_IMAGE_SEARCH,
            headers=_pexels_headers(),
            params={"query": food_query, "per_page": 3, "orientation": "portrait", "size": "large"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        photos = data.get("photos", [])
        if photos:
            return photos[0]["src"].get("large2x", photos[0]["src"]["large"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pexels image search failed for '%s': %s", query, exc)
    return None


def _search_unsplash_image(query: str) -> str | None:
    """Return the URL of a portrait food photo from Unsplash for *query*.

    Requires ``UNSPLASH_ACCESS_KEY`` to be set; returns None gracefully
    if the key is absent or the request fails.
    """
    api_key = getattr(config, "UNSPLASH_ACCESS_KEY", None)
    if not api_key:
        return None
    try:
        resp = requests.get(
            _UNSPLASH_SEARCH,
            headers={"Authorization": f"Client-ID {api_key}"},
            params={"query": query, "per_page": 3, "orientation": "portrait"},
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        results = data.get("results", [])
        if results:
            urls_obj = results[0].get("urls", {})
            return urls_obj.get("regular") or urls_obj.get("full")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unsplash image search failed for '%s': %s", query, exc)
    return None


def _download_file(url: str, suffix: str) -> Path:
    """Stream-download *url* to a named temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                fh.write(chunk)
    return tmp_path


# ---------------------------------------------------------------------------
# MoviePy helpers
# ---------------------------------------------------------------------------
def _resize_clip(clip: Any, w: int, h: int) -> Any:
    """Resize and centre-crop *clip* to exactly *w* × *h* pixels."""
    clip_w, clip_h = clip.size
    scale = max(w / clip_w, h / clip_h)
    resized = clip.resize(scale)
    x1 = (resized.w - w) / 2
    y1 = (resized.h - h) / 2
    return resized.crop(x1=x1, y1=y1, x2=x1 + w, y2=y1 + h)


def _ken_burns_effect(clip: Any, w: int, h: int, zoom_ratio: float = 0.08) -> Any:
    """Apply a slow Ken Burns zoom effect to a static image clip."""
    duration = clip.duration

    def _zoom_frame(clip_get_frame: Any, t: float) -> Any:
        import numpy as np
        frame = clip_get_frame(t)
        progress = t / duration if duration > 0 else 0
        current_zoom = 1.0 + zoom_ratio * progress
        fh, fw = frame.shape[:2]
        new_w = int(fw / current_zoom)
        new_h = int(fh / current_zoom)
        x1 = (fw - new_w) // 2
        y1 = (fh - new_h) // 2
        cropped = frame[y1:y1 + new_h, x1:x1 + new_w]
        pil_img = Image.fromarray(cropped)
        pil_img = pil_img.resize((fw, fh), Image.Resampling.LANCZOS)
        return np.array(pil_img)

    return clip.fl(_zoom_frame)


def _clean_text_for_display(text: str) -> str:
    """Sanitise *text* for on-screen subtitle display."""
    import re as _re
    cleaned = _re.sub(r"<[^>]+>", " ", text)
    cleaned = _re.sub(r"&[a-zA-Z]+;", " ", cleaned)
    cleaned = _re.sub(r"&#x?[0-9a-fA-F]+;", " ", cleaned)
    cleaned = cleaned.replace("<", " ").replace(">", " ")
    # Strip emoji that don't render cleanly in MoviePy TextClip
    cleaned = _re.sub(r"[\U00010000-\U0010ffff]", " ", cleaned)
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _split_into_chunks(text: str, max_words: int = 4) -> list[str]:
    """Break *text* into short word-burst chunks for meme-style captions."""
    import re
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.replace("\n", " ").strip())
    chunks: list[str] = []
    for sentence in raw_sentences:
        sentence = sentence.strip().rstrip(".!?")
        if not sentence:
            continue
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
        else:
            for start in range(0, len(words), max_words):
                chunk = " ".join(words[start: start + max_words])
                if chunk:
                    chunks.append(chunk)
    return [c for c in chunks if c]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a ``#RRGGBB`` hex string to an ``(R, G, B)`` tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _make_glow_pill_image(width: int, height: int, radius: int,
                          bg_color: tuple[int, int, int],
                          bg_opacity: float,
                          glow_color: tuple[int, int, int],
                          glow_radius: int) -> Any:
    """Create a rounded-rectangle pill with a soft neon glow halo."""
    import numpy as np

    pad = glow_radius
    total_w = width + pad * 2
    total_h = height + pad * 2
    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    glow_layers = max(4, glow_radius // 3)
    for layer in range(glow_layers, 0, -1):
        shrink = int((layer / glow_layers) * pad)
        alpha = int(60 * (1 - layer / glow_layers))
        rect = [(shrink, shrink), (total_w - 1 - shrink, total_h - 1 - shrink)]
        draw.rounded_rectangle(rect, radius=radius + pad - shrink,
                               fill=(*glow_color, alpha))

    pill_alpha = int(255 * bg_opacity)
    pill_rect = [(pad, pad), (pad + width - 1, pad + height - 1)]
    draw.rounded_rectangle(pill_rect, radius=radius, fill=(*bg_color, pill_alpha))

    return np.array(canvas), pad


def _make_rounded_rect_image(width: int, height: int, radius: int,
                              color: tuple[int, int, int],
                              opacity: float) -> Any:
    """Create a rounded-rectangle RGBA image for subtitle backgrounds."""
    import numpy as np
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    alpha = int(255 * opacity)
    fill = (*color, alpha)
    draw.rounded_rectangle([(0, 0), (width - 1, height - 1)], radius=radius, fill=fill)
    return np.array(img)


def _adaptive_font_size(chunk: str, base_size: int) -> int:
    """Return a font size scaled for comedy impact — short bursts render larger."""
    words = len(chunk.split())
    if words <= 1:
        return min(int(base_size * 1.25), 115)   # MAXIMUM POP for single words
    if words == 2:
        return min(int(base_size * 1.15), 105)
    if words <= 3:
        return base_size
    if words <= 4:
        return max(int(base_size * 0.90), 65)
    return max(int(base_size * 0.80), 58)


def _make_vignette_clip(w: int, h: int, duration: float) -> Any:
    """Create a cinematic dark-edge vignette as a transparent ImageClip."""
    import numpy as np
    from moviepy.editor import ImageClip  # type: ignore[import]

    _VIG_INNER_RADIUS = 0.35
    _VIG_FALLOFF = 1.1
    _VIG_MAX_ALPHA = 175

    img = np.zeros((h, w, 4), dtype=np.uint8)
    cx, cy = w / 2.0, h / 2.0
    y_idx, x_idx = np.mgrid[0:h, 0:w]
    nx = (x_idx - cx) / cx
    ny = (y_idx - cy) / cy
    dist = np.sqrt(nx ** 2 + ny ** 2)
    alpha_norm = np.clip((dist - _VIG_INNER_RADIUS) / _VIG_FALLOFF, 0.0, 1.0)
    img[:, :, 3] = (alpha_norm * _VIG_MAX_ALPHA).astype(np.uint8)
    return ImageClip(img, ismask=False, transparent=True).set_duration(duration)


def _build_caption_clips(script_text: str, total_duration: float, video_w: int, video_h: int,
                         start_offset: float = 0.0) -> list[Any]:
    """Create bold meme-style TikTok word-burst captions with neon comedy colours.

    Features:
    - Single caption zone at the lower third.
    - Neon glow pill backgrounds (orange-red / gold / spring green palette).
    - Word-proportional timing so each burst stays readable.
    - Adaptive font: 1-word bursts render larger for maximum comedy impact.
    - Bold uppercase text with thick stroke for contrast on any background.
    - Soft crossfade between bursts for a polished feel.
    """
    try:
        from moviepy.editor import TextClip, ImageClip  # type: ignore[import]
    except Exception:  # noqa: BLE001
        return []

    chunks = _split_into_chunks(
        _clean_text_for_display(script_text), max_words=config.SUBTITLE_MAX_WORDS
    )
    if not chunks:
        return []

    subtitle_delay = getattr(config, "SUBTITLE_DELAY", 0.25)
    end_buffer = getattr(config, "SUBTITLE_END_BUFFER", 0.4)
    start_offset += subtitle_delay

    available_duration = total_duration - start_offset - end_buffer
    if available_duration <= 0:
        available_duration = total_duration - start_offset
        if available_duration <= 0:
            available_duration = total_duration
            start_offset = subtitle_delay

    if getattr(config, "SUBTITLE_WORD_TIMING", True) and len(chunks) > 1:
        word_counts = [max(1, len(c.split())) for c in chunks]
        total_words = sum(word_counts)
        chunk_durations = [available_duration * wc / total_words for wc in word_counts]
    else:
        chunk_durations = [available_duration / len(chunks)] * len(chunks)

    chunk_starts: list[float] = []
    t = start_offset
    for dur in chunk_durations:
        chunk_starts.append(t)
        t += dur

    clips: list[Any] = []

    y_pos = int(video_h * getattr(config, "SUBTITLE_POSITION", 0.72))

    # Comedy colour palette: orange-red → gold → spring green (cycling)
    highlight  = getattr(config, "SUBTITLE_HIGHLIGHT_COLOR",  "#FF4500")
    secondary  = getattr(config, "SUBTITLE_SECONDARY_COLOR",  "#FFD700")
    accent     = getattr(config, "SUBTITLE_ACCENT_COLOR",     "#00FF7F")
    color_palette = [highlight, "white", secondary, highlight, accent, "white", secondary]

    corner_radius  = getattr(config, "SUBTITLE_BG_CORNER_RADIUS", 28)
    shadow_offset  = getattr(config, "SUBTITLE_SHADOW_OFFSET", 3)
    use_glow       = getattr(config, "SUBTITLE_GLOW", True)
    glow_color_hex = getattr(config, "SUBTITLE_GLOW_COLOR", "#FFD700")
    glow_radius    = getattr(config, "SUBTITLE_GLOW_RADIUS", 18)
    all_caps       = getattr(config, "SUBTITLE_ALL_CAPS", True)
    font_fallbacks = [getattr(config, "SUBTITLE_FONT", "Liberation-Sans-Bold")]
    font_fallbacks.extend(getattr(config, "SUBTITLE_FONT_FALLBACKS", []))
    seen_fonts: set[str] = set()
    ordered_fonts: list[str] = []
    for f in font_fallbacks:
        if f and f not in seen_fonts:
            ordered_fonts.append(f)
            seen_fonts.add(f)
    stroke_w       = getattr(config, "SUBTITLE_STROKE_WIDTH", 6)
    base_font_size = getattr(config, "SUBTITLE_FONT_SIZE", 92)

    glow_rgb = _hex_to_rgb(glow_color_hex)

    for i, chunk in enumerate(chunks):
        start = chunk_starts[i]
        dur   = chunk_durations[i]
        crossfade = min(0.12, dur * 0.18)
        color = color_palette[i % len(color_palette)]
        display_text = chunk.upper() if all_caps else chunk

        font_size = (
            _adaptive_font_size(chunk, base_font_size)
            if getattr(config, "SUBTITLE_ADAPTIVE_FONT", True)
            else base_font_size
        )

        try:
            txt_clip = None
            chosen_font: str | None = None
            last_font_exc: Exception | None = None
            for candidate_font in ordered_fonts:
                try:
                    txt_clip = TextClip(
                        display_text,
                        fontsize=font_size,
                        font=candidate_font,
                        color=color,
                        stroke_color="black",
                        stroke_width=stroke_w,
                        method="caption",
                        size=(video_w - 120, None),
                        align="center",
                    )
                    chosen_font = candidate_font
                    break
                except Exception as exc:  # noqa: BLE001
                    last_font_exc = exc
                    logger.debug(
                        "Subtitle font '%s' unavailable (%s): %s",
                        candidate_font,
                        type(exc).__name__,
                        exc,
                    )
            if txt_clip is None:
                logger.warning(
                    "Subtitle clip %d skipped: no usable subtitle font (%s: %s)",
                    i,
                    type(last_font_exc).__name__ if last_font_exc else "UnknownError",
                    last_font_exc,
                )
                continue
            txt_w, txt_h = txt_clip.size
            pad_x, pad_y = 36, 20

            bg_w = txt_w + pad_x * 2
            bg_h = txt_h + pad_y * 2

            if use_glow:
                bg_array, glow_pad = _make_glow_pill_image(
                    bg_w, bg_h, corner_radius,
                    bg_color=(8, 8, 8), bg_opacity=config.SUBTITLE_BG_OPACITY,
                    glow_color=glow_rgb, glow_radius=glow_radius,
                )
            else:
                bg_array = _make_rounded_rect_image(
                    bg_w, bg_h, corner_radius,
                    color=(8, 8, 8), opacity=config.SUBTITLE_BG_OPACITY,
                )
                glow_pad = 0

            pill_y = y_pos - bg_h // 2 - glow_pad
            bg_clip = (
                ImageClip(bg_array, ismask=False, transparent=True)
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", pill_y))
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            shadow_clip = (
                TextClip(
                    display_text,
                    fontsize=font_size,
                    font=chosen_font,
                    color="#000000",
                    stroke_color="#000000",
                    stroke_width=stroke_w + 2,
                    method="caption",
                    size=(video_w - 120, None),
                    align="center",
                )
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos - txt_h // 2 + shadow_offset))
                .set_opacity(0.45)
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            txt_clip = (
                txt_clip
                .set_start(start)
                .set_duration(dur)
                .set_position(("center", y_pos - txt_h // 2))
                .crossfadein(crossfade)
                .crossfadeout(crossfade)
            )

            clips.extend([bg_clip, shadow_clip, txt_clip])

        except Exception as exc:  # noqa: BLE001
            logger.warning("Caption clip %d skipped: %s", i, exc)

    return clips


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_video(
    audio_path: Path,
    script_text: str,
    scenes: list[str],
    audio_duration: float,
    hook_text: str = "",
    music_path: Path | None = None,
) -> Path:
    """Create a vertical 1080 × 1920 YouTube Shorts MP4 food making video.

    Fetches food-themed stock footage from Pexels, Pixabay, and Unsplash,
    applies warm vibrant colour grading, adds engaging captions, and exports a
    polished food short optimised for YouTube Shorts.

    Args:
        audio_path:     Path to the TTS MP3 audio file.
        script_text:    Full narration script (hook + body + CTA).  Every
                        spoken word is captioned in a single lower-third band.
        scenes:         List of scene description strings (used as food stock
                        search queries for Pexels, Pixabay, and Unsplash).
        audio_duration: Duration in seconds of the TTS audio.
        hook_text:      Kept for API compatibility.
        music_path:     Optional path to a background music MP3 supplied by
                        the pipeline (e.g. downloaded via music_selector).
                        When ``None``, falls back to the static
                        ``BG_MUSIC_PATH`` from config if it exists.

    Returns:
        Path to the exported MP4 file.

    Raises:
        RuntimeError: If video creation fails.
    """
    try:
        from moviepy.editor import (  # type: ignore[import]
            AudioFileClip,
            CompositeAudioClip,
            CompositeVideoClip,
            ColorClip,
            ImageClip,
            VideoFileClip,
            afx,
            concatenate_videoclips,
            vfx,
        )
    except ImportError as exc:
        raise RuntimeError("moviepy is not installed") from exc

    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    target_duration = audio_duration if audio_duration > 0 else config.VIDEO_DURATION_TARGET
    transition_dur = getattr(config, "VIDEO_TRANSITION_DURATION", 0.35)
    downloaded: list[Path] = []
    video_clips: list[Any] = []

    try:
    # ------------------------------------------------------------------
    # 1. Fetch food-themed stock footage for each scene
    # ------------------------------------------------------------------
        time_per_scene = target_duration / max(len(scenes), 1)
        for scene_idx, scene in enumerate(scenes):
            clip_added = False

            video_urls = _search_pexels_video(scene, per_page=5)
            for url in video_urls:
                try:
                    clip_path = _download_file(url, ".mp4")
                    downloaded.append(clip_path)
                    vc = VideoFileClip(str(clip_path), audio=False)
                    scene_dur = time_per_scene + transition_dur
                    if vc.duration < scene_dur:
                        loops = math.ceil(scene_dur / vc.duration)
                        vc = vc.loop(n=loops)
                    if getattr(config, "VIDEO_CLIP_RANDOM_START", True):
                        max_start = max(0.0, vc.duration - scene_dur)
                        if max_start > 1.0:
                            start_t = random.uniform(0.0, max_start)
                            vc = vc.subclip(start_t, start_t + scene_dur)
                        else:
                            vc = vc.subclip(0, scene_dur)
                    else:
                        vc = vc.subclip(0, scene_dur)
                    vc = _resize_clip(vc, w, h)
                    video_clips.append(vc)
                    clip_added = True
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to load video from Pexels: %s", exc)

            if not clip_added:
                # Try Unsplash as additional image fallback
                unsplash_url = _search_unsplash_image(f"{scene} food")
                if not unsplash_url:
                    img_url = _search_pexels_image(scene)
                else:
                    img_url = unsplash_url
                if img_url:
                    try:
                        img_path = _download_file(img_url, ".jpg")
                        downloaded.append(img_path)
                        scene_dur = time_per_scene + transition_dur
                        ic = ImageClip(str(img_path)).set_duration(scene_dur)
                        ic = _resize_clip(ic, w, h)
                        ic = _ken_burns_effect(ic, w, h, zoom_ratio=0.08)
                        video_clips.append(ic)
                        clip_added = True
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to load image from stock source: %s", exc)

            if not clip_added:
                logger.warning("No footage for scene '%s'; trying alternative sources", scene)
                # Try footage_alternatives (Coverr, Videvo, AI placeholder)
                try:
                    from src.footage_alternatives import fetch_fallback_clip  # noqa: PLC0415

                    scene_dur = time_per_scene + transition_dur
                    alt_path = fetch_fallback_clip(
                        scene_description=scene,
                        duration=scene_dur,
                        width=w,
                        height=h,
                        scene_index=scene_idx,
                    )
                    if alt_path and alt_path.suffix.lower() == ".mp4":
                        downloaded.append(alt_path)
                        vc = VideoFileClip(str(alt_path), audio=False)
                        if vc.duration < scene_dur:
                            loops = math.ceil(scene_dur / vc.duration)
                            vc = vc.loop(n=loops)
                        vc = vc.subclip(0, scene_dur)
                        vc = _resize_clip(vc, w, h)
                        video_clips.append(vc)
                        clip_added = True
                        logger.info("Used alternative footage source for scene '%s'", scene)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Footage alternatives failed for scene '%s': %s", scene, exc)

            if not clip_added:
                logger.warning("No footage for scene '%s'; using warm gradient placeholder", scene)
                scene_dur = time_per_scene + transition_dur
                # Warm food-themed gradient placeholder
                placeholder = ColorClip(size=(w, h), color=(180, 80, 20)).set_duration(scene_dur)
                video_clips.append(placeholder)

        # ------------------------------------------------------------------
        # 2. Concatenate clips with crossfade transitions
        # ------------------------------------------------------------------
        if not video_clips:
            raise RuntimeError("No video clips could be assembled")

        if len(video_clips) > 1 and transition_dur > 0:
            base = concatenate_videoclips(
                video_clips,
                method="compose",
                padding=-transition_dur,
            )
        else:
            base = concatenate_videoclips(video_clips, method="compose")

        if base.duration > target_duration:
            base = base.subclip(0, target_duration)

        # ------------------------------------------------------------------
        # 3. Overlay TTS audio (mixed with optional background music)
        # ------------------------------------------------------------------
        tts_audio = AudioFileClip(str(audio_path))
        target_duration = _resolve_target_duration(
            requested_audio_duration=audio_duration,
            default_duration=config.VIDEO_DURATION_TARGET,
            measured_tts_duration=getattr(tts_audio, "duration", None),
        )

        base = _fit_base_video_duration(base, target_duration, vfx)

        # Prefer dynamically-supplied music_path; fall back to static BG_MUSIC_PATH
        effective_music_path = music_path if music_path is not None else Path(config.BG_MUSIC_PATH)

        if effective_music_path.exists() and config.BG_MUSIC_VOLUME > 0:
            try:
                fade_dur = getattr(config, "MUSIC_FADE_DURATION", 1.0)
                bg_audio = AudioFileClip(str(effective_music_path)).volumex(config.BG_MUSIC_VOLUME)
                bg_audio = _fit_bg_audio_to_duration(bg_audio, target_duration, afx)
                bg_audio = bg_audio.audio_fadein(fade_dur).audio_fadeout(fade_dur * 2)
                mixed_audio = CompositeAudioClip([bg_audio, tts_audio])
                base = base.set_audio(mixed_audio)
                logger.info("Background music mixed in at volume %.2f", config.BG_MUSIC_VOLUME)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not mix background music: %s — using TTS only", exc)
                base = base.set_audio(tts_audio)
        else:
            base = base.set_audio(tts_audio)

        # ------------------------------------------------------------------
        # 4. Build engaging captions — bold warm-toned word bursts for food content
        # ------------------------------------------------------------------
        caption_clips = _build_caption_clips(
            script_text, target_duration, w, h, start_offset=0.0
        )

        # ------------------------------------------------------------------
        # 5. Compose layers: base + captions + optional vignette
        # ------------------------------------------------------------------
        layers: list[Any] = [base] + caption_clips
        if getattr(config, "VIDEO_VIGNETTE", True):
            try:
                vignette = _make_vignette_clip(w, h, target_duration)
                layers.append(vignette)
                logger.debug("Cinematic vignette overlay applied")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vignette overlay failed: %s", exc)

        final = CompositeVideoClip(layers, size=(w, h)) if len(layers) > 1 else base

        # ------------------------------------------------------------------
        # 5b. Warm food colour grade — vibrant, appetising palette
        #     Boosts warm tones (reds and ambers) for appetite appeal.
        # ------------------------------------------------------------------
        if getattr(config, "VIDEO_COLOR_GRADE", True):
            try:
                import numpy as np

                def _animation_grade_frame(frame: Any) -> Any:
                    """Apply a warm food-style colour grade.

                    Boosts warm tones (reds and ambers) for appetite appeal
                    while maintaining natural food colours.
                    """
                    f = frame.astype("float32") / 255.0
                    # Stronger S-curve contrast for punchy animation feel
                    f = np.clip(f * 1.12 - 0.06, 0.0, 1.0)
                    # Saturation boost: push colours away from grey (luminance 0.299R + 0.587G + 0.114B)
                    lum = (0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2])
                    lum = lum[:, :, np.newaxis]
                    sat_boost = 1.25
                    f = np.clip(lum + sat_boost * (f - lum), 0.0, 1.0)
                    # Warm-cool comic tint: warm reds, cool blues stay vivid
                    f[:, :, 0] = np.clip(f[:, :, 0] * 1.05, 0.0, 1.0)  # red channel boost
                    f[:, :, 1] = np.clip(f[:, :, 1] * 1.02, 0.0, 1.0)  # green slight boost
                    return (f * 255).astype("uint8")

                final = final.fl_image(_animation_grade_frame)
                logger.debug("Food colour grade applied (warm tone boost + vibrant contrast)")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Colour grade skipped: %s", exc)

        # ------------------------------------------------------------------
        # 6. Fade-in / fade-out
        # ------------------------------------------------------------------
        final = final.fadein(0.5).fadeout(0.7)

        # ------------------------------------------------------------------
        # 7. Export
        # ------------------------------------------------------------------
        out_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = Path(out_tmp.name)
        out_tmp.close()

        logger.info("Rendering comedy animation video to '%s' …", out_path)
        final.write_videofile(
            str(out_path),
            fps=config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset=config.VIDEO_PRESET,
            bitrate=config.VIDEO_BITRATE,
            audio_bitrate=config.AUDIO_BITRATE,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            logger=None,
        )
        logger.info("Comedy animation video rendered successfully: '%s'", out_path)
        return out_path

    finally:
        for p in downloaded:
            try:
                p.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
