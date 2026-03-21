"""Focused tests for src/pipeline.py thumbnail removal flow."""

import sys
import unittest
from unittest.mock import MagicMock, patch


class TestPipelineWithoutThumbnail(unittest.TestCase):
    """Ensure the pipeline no longer imports or passes custom thumbnails."""

    def setUp(self):
        sys.modules.pop("src.pipeline", None)
        import src.pipeline as pipeline
        self.pipeline = pipeline

    @patch("src.pipeline._cleanup")
    def test_run_pipeline_uploads_without_thumbnail_argument(self, mock_cleanup):
        script_data = {
            "title": "Test title",
            "script": "Test script",
            "caption_script": "Test caption",
            "hook": "Test hook",
            "scenes": ["scene a", "scene b"],
            "tags": ["food", "recipe"],
            "description": "desc",
        }

        with patch("src.uploader.validate_credentials"), \
             patch("src.trending.get_best_topic", return_value="topic"), \
             patch("src.enhanced_scriptwriter.generate_enhanced_script", return_value=script_data), \
             patch("src.tts.generate_speech", return_value=(MagicMock(), 10.0)), \
             patch("src.music_selector.get_music_for_scenes", return_value=None), \
             patch("src.video_creator.create_video", return_value=MagicMock()), \
             patch("src.uploader.upload_video", return_value=("abc123", "https://youtube.com/watch?v=abc123")) as mock_upload:
            self.pipeline.run_pipeline()

        self.assertTrue(mock_upload.called)
        _, kwargs = mock_upload.call_args
        self.assertNotIn("thumbnail_path", kwargs)
        mock_cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
