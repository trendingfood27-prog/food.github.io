"""
pipeline.py — Main orchestrator for the Food Making Videos Factory pipeline.

Runs all steps in sequence:
  1. Fetch the best trending topic (food-scored)
  2. Generate a professional food script (via OpenRouter AI or templates)
  3. Convert the script to speech (TTS — female voice)
  4. Create the food-style video
  5. Generate a food thumbnail
  6. Upload to YouTube

Usage::

    python -m src.pipeline
"""

import logging
import time
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _cleanup(*paths: Path | None) -> None:
    """Delete temporary files, ignoring errors."""
    for p in paths:
        if p is not None:
            try:
                p.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass


def run_pipeline() -> None:
    """Execute the full Food Making Videos Factory creation and upload pipeline."""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("\U0001f373 Food Making Videos Factory — pipeline starting")
    logger.info("=" * 60)

    audio_path: Path | None = None
    video_path: Path | None = None
    thumb_path: Path | None = None

    try:
        # ------------------------------------------------------------------
        # Step 0: Validate YouTube credentials (fail fast before heavy work)
        # ------------------------------------------------------------------
        logger.info("[0/6] \U0001f511 Validating YouTube credentials…")
        from src.uploader import validate_credentials  # noqa: PLC0415

        validate_credentials()
        logger.info("      Credentials OK")

        # ------------------------------------------------------------------
        # Step 1: Find best food topic
        # ------------------------------------------------------------------
        logger.info("[1/6] \U0001f525 Finding viral food topic — fetching trending topics…")
        from src.trending import get_best_topic  # noqa: PLC0415

        topic = get_best_topic()
        logger.info("      Food topic selected: '%s'", topic)

        # ------------------------------------------------------------------
        # Step 2: Generate professional food script via OpenRouter AI
        # ------------------------------------------------------------------
        logger.info("[2/6] \u270d\ufe0f  Writing script — generating AI food script for: '%s'…", topic)
        from src.scriptwriter import generate_script  # noqa: PLC0415

        script_data = generate_script(topic)
        title = script_data["title"]
        script_text = script_data["script"]
        caption_text = script_data["caption_script"]
        hook_text = script_data["hook"]
        scenes = script_data["scenes"]
        tags = script_data["tags"]
        description = script_data["description"]
        logger.info("      Food video title: '%s'", title)

        # ------------------------------------------------------------------
        # Step 3: Text-to-speech (professional female voice narration)
        # ------------------------------------------------------------------
        logger.info("[3/6] \U0001f3a4 Narrating — generating professional female TTS audio…")
        from src.tts import generate_speech  # noqa: PLC0415

        audio_path, audio_duration = generate_speech(script_text)
        logger.info("      Audio duration: %.2f s", audio_duration)

        # ------------------------------------------------------------------
        # Step 4: Create food-style video
        # ------------------------------------------------------------------
        logger.info("[4/6] \U0001f3ac Assembling — creating food video with stock footage…")
        from src.video_creator import create_video  # noqa: PLC0415

        video_path = create_video(audio_path, script_text, scenes, audio_duration,
                                  hook_text=hook_text)
        logger.info("      Video path: '%s'", video_path)

        # ------------------------------------------------------------------
        # Step 5: Generate food thumbnail
        # ------------------------------------------------------------------
        logger.info("[5/6] \U0001f5bc\ufe0f  Designing thumbnail — generating food content thumbnail…")
        from src.thumbnail import create_thumbnail  # noqa: PLC0415

        thumb_path = create_thumbnail(title, topic)
        logger.info("      Thumbnail path: '%s'", thumb_path)

        # ------------------------------------------------------------------
        # Step 6: Upload to YouTube
        # ------------------------------------------------------------------
        logger.info("[6/6] \U0001f680 Upload and go viral — uploading to YouTube…")
        from src.uploader import upload_video  # noqa: PLC0415

        video_id, video_url = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumb_path,
        )
        logger.info("      Upload complete: %s", video_url)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("\U0001f389 Food Making Videos Factory — pipeline completed in %.1f seconds", elapsed)
        logger.info("  Topic      : %s", topic)
        logger.info("  Title      : %s", title)
        logger.info("  Video ID   : %s", video_id)
        logger.info("  URL        : %s", video_url)
        logger.info("=" * 60)

    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - start_time
        logger.error("\U0001f4a5 Pipeline failed after %.1f seconds: %s", elapsed, exc, exc_info=True)
    finally:
        _cleanup(audio_path, video_path, thumb_path)
        logger.info("\U0001f9f9 Temporary files cleaned up")


if __name__ == "__main__":
    run_pipeline()
