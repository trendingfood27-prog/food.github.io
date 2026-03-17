"""
tests/test_enhanced_scriptwriter.py — Unit tests for src/enhanced_scriptwriter.py

Tests the step-by-step enhanced script generator with no external API calls.
Run with: python -m pytest tests/ -v
"""

import sys
import unittest
from unittest.mock import MagicMock

# Stub heavy optional imports
for mod in ("edge_tts", "moviepy", "moviepy.editor",
            "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
            "pydub", "mutagen", "mutagen.mp3",
            "googleapiclient", "googleapiclient.discovery",
            "httpx"):
    sys.modules.setdefault(mod, MagicMock())


class TestGenerateEnhancedScript(unittest.TestCase):
    """Tests for enhanced_scriptwriter.generate_enhanced_script()."""

    def setUp(self):
        from src.enhanced_scriptwriter import generate_enhanced_script
        self.generate_enhanced_script = generate_enhanced_script

    def test_returns_dict(self):
        result = self.generate_enhanced_script("pasta carbonara")
        self.assertIsInstance(result, dict)

    def test_contains_base_keys(self):
        """Enhanced output must still have all base scriptwriter keys."""
        result = self.generate_enhanced_script("chicken recipe")
        base_keys = {"title", "script", "caption_script", "hook", "scenes", "tags", "description"}
        for key in base_keys:
            self.assertIn(key, result, f"Missing base key: {key!r}")

    def test_contains_enhanced_keys(self):
        """Enhanced output must have the additional step-by-step keys."""
        result = self.generate_enhanced_script("pasta carbonara")
        enhanced_keys = {"ingredients", "steps", "prep_time", "cook_time", "total_time",
                         "tips", "variations", "beat_markers"}
        for key in enhanced_keys:
            self.assertIn(key, result, f"Missing enhanced key: {key!r}")

    def test_ingredients_is_non_empty_list(self):
        result = self.generate_enhanced_script("chicken curry")
        self.assertIsInstance(result["ingredients"], list)
        self.assertGreater(len(result["ingredients"]), 0)

    def test_steps_is_non_empty_list(self):
        result = self.generate_enhanced_script("pasta carbonara")
        self.assertIsInstance(result["steps"], list)
        self.assertGreater(len(result["steps"]), 0)

    def test_steps_are_strings(self):
        result = self.generate_enhanced_script("chicken stir fry")
        for step in result["steps"]:
            self.assertIsInstance(step, str, "Each step must be a string")
            self.assertTrue(step.strip(), "Steps must not be blank")

    def test_timing_is_positive_integers(self):
        result = self.generate_enhanced_script("quick pasta recipe")
        self.assertIsInstance(result["prep_time"], int)
        self.assertIsInstance(result["cook_time"], int)
        self.assertIsInstance(result["total_time"], int)
        self.assertGreater(result["prep_time"], 0)
        self.assertGreater(result["cook_time"], 0)
        self.assertGreater(result["total_time"], 0)

    def test_total_time_is_sum_of_prep_and_cook(self):
        result = self.generate_enhanced_script("pasta recipe")
        self.assertEqual(result["total_time"], result["prep_time"] + result["cook_time"])

    def test_tips_is_list_of_strings(self):
        result = self.generate_enhanced_script("salmon fillet")
        self.assertIsInstance(result["tips"], list)
        for tip in result["tips"]:
            self.assertIsInstance(tip, str)

    def test_variations_is_list_of_strings(self):
        result = self.generate_enhanced_script("curry recipe")
        self.assertIsInstance(result["variations"], list)
        for var in result["variations"]:
            self.assertIsInstance(var, str)

    def test_beat_markers_is_list_of_dicts(self):
        result = self.generate_enhanced_script("steak recipe")
        self.assertIsInstance(result["beat_markers"], list)
        for marker in result["beat_markers"]:
            self.assertIsInstance(marker, dict)
            self.assertIn("time_offset", marker)
            self.assertIn("cue", marker)

    def test_beat_markers_have_non_negative_time_offsets(self):
        result = self.generate_enhanced_script("pasta")
        for marker in result["beat_markers"]:
            self.assertGreaterEqual(marker["time_offset"], 0.0)

    def test_enhanced_script_contains_steps(self):
        """The script text should contain step references for structured how-to content."""
        result = self.generate_enhanced_script("pasta carbonara")
        script_lower = result["script"].lower()
        has_step = "step" in script_lower or "first" in script_lower or "start" in script_lower
        self.assertTrue(has_step, "Enhanced script should contain step-by-step language")

    def test_scenes_is_non_empty_list(self):
        result = self.generate_enhanced_script("chicken wings")
        self.assertIsInstance(result["scenes"], list)
        self.assertGreater(len(result["scenes"]), 0)

    def test_description_contains_timing(self):
        """Enhanced description should mention prep/cook time."""
        result = self.generate_enhanced_script("quick pasta")
        desc = result["description"]
        has_time = any(word in desc for word in ["min", "Prep:", "Cook:", "Total:"])
        self.assertTrue(has_time, "Enhanced description should include timing information")

    def test_various_topics_do_not_raise(self):
        """Various food topics should generate enhanced scripts without crashing."""
        topics = [
            "pasta carbonara",
            "crispy chicken",
            "chocolate cake",
            "biryani",
            "vegan tacos",
            "",
            "quick 5 ingredient meal",
        ]
        for topic in topics:
            with self.subTest(topic=topic):
                try:
                    result = self.generate_enhanced_script(topic)
                    self.assertIn("title", result)
                except Exception as exc:
                    self.fail(f"generate_enhanced_script({topic!r}) raised: {exc}")

    def test_pasta_topic_uses_pasta_template(self):
        """Pasta topic should produce pasta-specific steps and ingredients (via AI or template)."""
        result = self.generate_enhanced_script("pasta carbonara")
        ingredients_text = " ".join(result["ingredients"]).lower()
        steps_text = " ".join(result["steps"]).lower()
        has_pasta_ingredients = "pasta" in ingredients_text or "olive oil" in ingredients_text
        has_pasta_steps = "pasta" in steps_text or "boil" in steps_text or "al dente" in steps_text
        self.assertTrue(has_pasta_ingredients or has_pasta_steps,
                        "Pasta topic should use pasta-specific content")


class TestFetchTimingViaOpenrouter(unittest.TestCase):
    """Tests for _fetch_timing_via_openrouter()."""

    def test_returns_none_without_api_key(self):
        """Should return None when no OPENROUTER_API_KEY is set."""
        import importlib
        import src.enhanced_scriptwriter as esw
        # Patch config and env so no key is available
        original = getattr(esw.config, "OPENROUTER_API_KEY", None)
        esw.config.OPENROUTER_API_KEY = None
        import os
        saved = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = esw._fetch_timing_via_openrouter("pasta")
            self.assertIsNone(result)
        finally:
            esw.config.OPENROUTER_API_KEY = original
            if saved is not None:
                os.environ["OPENROUTER_API_KEY"] = saved

    def test_returns_tuple_on_valid_ai_response(self):
        """Should return (prep, cook, total) tuple when API returns valid timing JSON."""
        import src.enhanced_scriptwriter as esw
        import json
        from unittest.mock import patch, MagicMock

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(
                {"prep_time": 10, "cook_time": 20, "total_time": 30}
            )}}]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch.object(esw.config, "OPENROUTER_API_KEY", "fake-key"), \
             patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = fake_resp
            result = esw._fetch_timing_via_openrouter("pasta carbonara")

        self.assertIsNotNone(result)
        prep, cook, total = result
        self.assertEqual(prep, 10)
        self.assertEqual(cook, 20)
        self.assertEqual(total, 30)

    def test_returns_none_on_api_failure(self):
        """Should return None when the API call raises an exception."""
        import src.enhanced_scriptwriter as esw
        from unittest.mock import patch

        with patch.object(esw.config, "OPENROUTER_API_KEY", "fake-key"), \
             patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = Exception("Network error")
            result = esw._fetch_timing_via_openrouter("pasta carbonara")

        self.assertIsNone(result)


class TestFetchIngredientsViaOpenrouter(unittest.TestCase):
    """Tests for _fetch_ingredients_via_openrouter()."""

    def test_returns_none_without_api_key(self):
        """Should return None when no OPENROUTER_API_KEY is set."""
        import src.enhanced_scriptwriter as esw
        import os
        original = getattr(esw.config, "OPENROUTER_API_KEY", None)
        esw.config.OPENROUTER_API_KEY = None
        saved = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = esw._fetch_ingredients_via_openrouter("pasta")
            self.assertIsNone(result)
        finally:
            esw.config.OPENROUTER_API_KEY = original
            if saved is not None:
                os.environ["OPENROUTER_API_KEY"] = saved

    def test_returns_list_on_valid_ai_response(self):
        """Should return a list of strings when API returns valid ingredients JSON."""
        import src.enhanced_scriptwriter as esw
        import json
        from unittest.mock import patch, MagicMock

        fake_ingredients = ["400g spaghetti", "200g guanciale", "4 egg yolks", "50g Pecorino"]
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(fake_ingredients)}}]
        }
        fake_resp.raise_for_status = MagicMock()

        with patch.object(esw.config, "OPENROUTER_API_KEY", "fake-key"), \
             patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = fake_resp
            result = esw._fetch_ingredients_via_openrouter("pasta carbonara")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("400g spaghetti", result)


if __name__ == "__main__":
    unittest.main()
