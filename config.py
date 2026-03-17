"""Central configuration for the Food Making Videos Factory pipeline."""

import os

# API Keys (loaded from GitHub Secrets / environment variables)
YOUTUBE_CLIENT_SECRET_JSON: str | None = os.getenv("YOUTUBE_CLIENT_SECRET")  # JSON string of OAuth2 client secret
YOUTUBE_TOKEN_JSON: str | None = os.getenv("YOUTUBE_TOKEN")  # JSON string of OAuth2 token
PEXELS_API_KEY: str | None = os.getenv("PEXELS_API_KEY")  # For stock footage (free tier)
NEWSAPI_KEY: str | None = os.getenv("NEWSAPI_KEY")  # NewsAPI.org key for trending headlines (optional)
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")  # OpenRouter AI key for script generation
PIXABAY_API_KEY: str | None = os.getenv("PIXABAY_API_KEY")  # Pixabay API key for additional stock footage
UNSPLASH_ACCESS_KEY: str | None = os.getenv("UNSPLASH_ACCESS_KEY")  # Unsplash API key for food photography

# Video settings
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920
VIDEO_FPS: int = 30
VIDEO_DURATION_TARGET: int = 55  # seconds target — optimal for food Shorts retention
FONT_SIZE: int = 60
FONT_COLOR: str = "white"
BG_MUSIC_VOLUME: float = 0.08
BG_MUSIC_PATH: str = "assets/bg_music.mp3"  # Relative path to background music file (leave empty to disable)

# ---------------------------------------------------------------------------
# Background music settings — scene-aware music selection and mixing
# ---------------------------------------------------------------------------
MUSIC_ENABLED: bool = True                   # Set False to disable background music entirely
MUSIC_VOLUME: float = BG_MUSIC_VOLUME        # Background music volume (0.0–1.0 relative to narration)
MUSIC_FADE_DURATION: float = 1.0             # Fade-in and fade-out duration in seconds
MUSIC_CACHE_DIR: str = "cache/music"         # Local cache directory for downloaded tracks

# Music source fallback chain — tried in order until one succeeds.
# Remove or reorder entries to customise behaviour.
#   "pixabay"          — Pixabay Music API (requires PIXABAY_API_KEY)
#   "free_music_archive" — Free Music Archive API (no API key required)
#   "freesound"        — Freesound API (requires FREESOUND_API_KEY, optional)
#   "incompetech"      — Kevin MacLeod CC BY tracks (no API key required)
#   "ccmixter"         — ccMixter Creative Commons community music (no API key)
#   "local_cache"      — Random rotation from previously-downloaded cache files
#   "silence"          — Locally-generated silent WAV (always succeeds)
MUSIC_SOURCE_PRIORITY: list = [
    "pixabay",
    "free_music_archive",
    "freesound",
    "incompetech",
    "ccmixter",
    "local_cache",
    "silence",
]

FREESOUND_API_KEY: str | None = os.getenv("FREESOUND_API_KEY")  # Optional — freesound.org API key

# ---------------------------------------------------------------------------
# Food content style settings
# ---------------------------------------------------------------------------
CONTENT_STYLE: str = "food making"               # content focus
ENGAGEMENT_LEVEL: str = "maximum"                # engagement intensity
FOOD_CATEGORIES: list = [
    "quick recipes",
    "cooking hacks",
    "meal prep",
    "food science",
    "kitchen tips",
    "restaurant-style at home",
    "healthy eating",
    "comfort food",
]
FOOD_PRESENTATION_STYLES: list = [
    "overhead flat lay",
    "close-up detail shots",
    "step-by-step preparation",
    "finished dish reveal",
    "ingredient showcase",
    "before and after",
]
HOOK_ZOOM: bool = True               # zoom effect on recipe reveals
FOOD_CAPTIONS: bool = True           # ingredient and step captions

# ---------------------------------------------------------------------------
# Subtitle / caption styling — bold, engaging word bursts for food content
# ---------------------------------------------------------------------------
SUBTITLE_FONT_SIZE: int = 92           # slightly larger for impact
SUBTITLE_FONT: str = "Liberation-Sans-Bold"  # fallback fonts tried in order by MoviePy
SUBTITLE_FONT_FALLBACKS: list = [      # tried in order if primary font is unavailable
    "Arial-Bold", "DejaVu-Sans-Bold", "FreeSans-Bold", "Liberation-Sans-Bold",
]
SUBTITLE_STROKE_WIDTH: int = 6         # thicker stroke = sharper legibility on any bg
SUBTITLE_BG_OPACITY: float = 0.82     # slightly more opaque pill for better contrast
SUBTITLE_HIGHLIGHT_COLOR: str = "#FF6B00"   # warm orange for food vibrancy
SUBTITLE_SECONDARY_COLOR: str = "#FFD700"   # golden yellow for warmth
SUBTITLE_ACCENT_COLOR: str = "#FF3366"      # red accent for urgency/CTAs
SUBTITLE_POSITION: float = 0.72        # vertical position (0 = top, 1 = bottom of frame)
SUBTITLE_MAX_WORDS: int = 4            # max words per caption burst
SUBTITLE_BG_CORNER_RADIUS: int = 28   # rounder pill for modern look
SUBTITLE_SHADOW_OFFSET: int = 3       # drop shadow offset in px
SUBTITLE_GLOW: bool = True             # neon glow behind pill background
SUBTITLE_GLOW_COLOR: str = "#FF6B00"  # glow colour (warm orange for food)
SUBTITLE_GLOW_RADIUS: int = 18        # glow blur radius in px
SUBTITLE_WORD_TIMING: bool = True      # scale each caption's duration by word count
SUBTITLE_ADAPTIVE_FONT: bool = True    # bigger font for short (1-2 word) power bursts
SUBTITLE_POP_SCALE: float = 1.25      # bigger pop for recipe reveals
SUBTITLE_ALL_CAPS: bool = True         # render captions in uppercase for impact
SUBTITLE_DELAY: float = 0.25          # seconds to delay captions so they trail speech (sync fix)
SUBTITLE_END_BUFFER: float = 0.4      # seconds of padding at the end; prevents captions outrunning speech

# ---------------------------------------------------------------------------
# Video encoding quality — high-bitrate for crisp 1080 × 1920 Shorts
# ---------------------------------------------------------------------------
VIDEO_PRESET: str = "slow"
VIDEO_BITRATE: str = "16000k"          # raised from 12000k for sharper quality
AUDIO_BITRATE: str = "320k"            # raised from 256k for cleaner audio
VIDEO_TRANSITION_DURATION: float = 0.35
VIDEO_VIGNETTE: bool = True            # cinematic dark-edge vignette overlay
VIDEO_COLOR_GRADE: bool = True         # vibrant, saturated colour grade for food appeal
VIDEO_CLIP_RANDOM_START: bool = True   # random clip start for visual variety per run

# ---------------------------------------------------------------------------
# TTS settings — female-only rotating voice pool, professional narration
# ---------------------------------------------------------------------------
TTS_VOICE: str = "en-US-JennyNeural"  # fallback voice if rotation is disabled
TTS_VOICE_ROTATE: bool = True          # True = pick a different voice each run
TTS_RATE: str = "+5%"                  # slightly faster pace for energy
TTS_VOLUME_NORMALIZE: bool = True      # normalize loudness with pydub

# Pexels fetch settings
PEXELS_PER_PAGE: int = 10  # more results = better footage variety

# Upload settings
YOUTUBE_CATEGORY_ID: str = "26"  # Howto & Style
PRIVACY_STATUS: str = "public"

# Scheduling
MAX_VIDEOS_PER_RUN: int = 1

# OpenRouter AI settings
OPENROUTER_MODEL: str = "openai/gpt-4o-mini"  # cost-effective model for script generation
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Footage alternative sources — additional video fallbacks beyond Pexels
# ---------------------------------------------------------------------------
COVERR_ENABLED: bool = True       # Coverr.co free stock videos (no API key required)
VIDEVO_ENABLED: bool = True       # Videvo.net free stock footage (no API key required)

# YouTube Data API key (optional) — enables CC video search as footage source
YOUTUBE_DATA_API_KEY: str | None = os.getenv("YOUTUBE_DATA_API_KEY")

# ---------------------------------------------------------------------------
# Virality optimization engine
# ---------------------------------------------------------------------------
VIRALITY_OPTIMIZATION_ENABLED: bool = True  # Log virality score report before upload
VIRALITY_MIN_SCORE: float = 0.0             # Minimum score to proceed (0.0 = always proceed)

# ---------------------------------------------------------------------------
# Viral tags generator — multi-tier tagging system
# ---------------------------------------------------------------------------
VIRAL_TAGS_ENABLED: bool = True   # Use advanced viral_tags_generator for 30-50 tags
VIRAL_TAGS_TARGET_COUNT: int = 45  # Target number of tags (30-50 range)

# ---------------------------------------------------------------------------
# Enhanced script writing — step-by-step instructions
# ---------------------------------------------------------------------------
ENHANCED_SCRIPT_ENABLED: bool = True  # Use enhanced_scriptwriter for step-by-step scripts
