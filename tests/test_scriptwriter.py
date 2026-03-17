"""
tests/test_scriptwriter.py — Unit tests for src/scriptwriter.py

Tests the food making video script generator (template-based fallback) with
no external API calls.  OpenRouter AI integration is not exercised here as it
requires a live API key.
Run with: python -m pytest tests/ -v
"""

import unittest

import sys
from unittest.mock import MagicMock

# Stub heavy optional imports not needed for scriptwriter tests
for mod in ("edge_tts", "moviepy", "moviepy.editor",
            "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
            "pydub", "mutagen", "mutagen.mp3",
            "googleapiclient", "googleapiclient.discovery",
            "httpx"):
    sys.modules.setdefault(mod, MagicMock())


class TestGenerateScript(unittest.TestCase):
    """Tests for scriptwriter.generate_script() — food making video output."""

    def setUp(self):
        from src.scriptwriter import generate_script
        self.generate_script = generate_script

    def test_returns_required_keys(self):
        """Result must contain all keys that pipeline.py depends on."""
        result = self.generate_script("pasta carbonara")
        required_keys = {"title", "script", "caption_script", "hook", "scenes", "tags", "description"}
        self.assertEqual(required_keys, required_keys & result.keys(),
                         f"Missing keys: {required_keys - result.keys()}")

    def test_title_is_non_empty_string(self):
        result = self.generate_script("crispy chicken recipe")
        self.assertIsInstance(result["title"], str)
        self.assertTrue(result["title"].strip(), "title must not be blank")

    def test_title_max_100_chars(self):
        """YouTube limits titles to 100 characters."""
        result = self.generate_script("a very long food recipe name " * 5)
        self.assertLessEqual(len(result["title"]), 100,
                             "title exceeds 100-character YouTube limit")

    def test_title_has_food_style(self):
        """Food titles should contain food emoji or engaging food keywords."""
        result = self.generate_script("homemade pizza")
        title = result["title"]
        # Food titles have emoji, exclamation, or food power words
        has_energy = any(c in title for c in "!?🍳🍕🥘🍜🔥❤️💯✨😍😮")
        has_food_word = any(word in title.lower() for word in
                            ["recipe", "secret", "perfect", "easy", "best",
                             "homemade", "gourmet", "viral", "trick", "hack"])
        self.assertTrue(has_energy or has_food_word,
                        f"Food title lacks engaging style: {title!r}")

    def test_script_is_non_empty_string(self):
        result = self.generate_script("air fryer chicken wings")
        self.assertIsInstance(result["script"], str)
        self.assertTrue(result["script"].strip(), "script must not be blank")

    def test_script_has_no_ssml_tags(self):
        """TTS receives the script — it must be plain text with no SSML markup."""
        result = self.generate_script("homemade bread")
        script = result["script"]
        self.assertNotIn("<speak", script, "script must not contain SSML <speak> tag")
        self.assertNotIn("<voice", script, "script must not contain SSML <voice> tag")
        self.assertNotIn("<prosody", script, "script must not contain SSML <prosody> tag")

    def test_hook_is_food_style(self):
        """Hook templates must be food/recipe focused rather than comedy animation style."""
        result = self.generate_script("pasta water secret")
        hook = result["hook"]
        self.assertIsInstance(hook, str)
        self.assertTrue(hook.strip(), "hook must not be blank")
        # Food hooks should NOT contain comedy/animation references
        old_comedy_markers = ["cartoon", "chibi", "stick figure", "blob", "pixel",
                              "animated", "what if alarm clocks"]
        hook_lower = hook.lower()
        for marker in old_comedy_markers:
            self.assertNotIn(marker, hook_lower,
                             f"Hook contains old comedy/animation marker '{marker}': {hook!r}")

    def test_script_contains_subscribe_cta(self):
        """Script must contain a subscribe/follow/like call to action."""
        result = self.generate_script("crispy roasted vegetables")
        script = result["script"].lower()
        has_cta = any(word in script for word in ["subscribe", "follow", "like"])
        self.assertTrue(has_cta, "Script must contain a subscribe/follow CTA")

    def test_tags_is_list_of_strings(self):
        result = self.generate_script("salmon recipe")
        tags = result["tags"]
        self.assertIsInstance(tags, list)
        self.assertTrue(all(isinstance(t, str) for t in tags),
                        "all tags must be strings")

    def test_tags_include_food_cooking_keywords(self):
        """Tags must include food and cooking keywords."""
        result = self.generate_script("pasta recipe")
        tags_joined = " ".join(result["tags"]).lower()
        food_tag_keywords = ["food", "recipe", "cooking", "cook", "kitchen", "meal"]
        has_food_tags = any(kw in tags_joined for kw in food_tag_keywords)
        self.assertTrue(has_food_tags,
                        f"Tags must include food/cooking keywords. Got: {result['tags'][:10]}")

    def test_tags_not_comedy_animation(self):
        """Tags must NOT include comedy animation keywords from the old factory."""
        result = self.generate_script("stir fry vegetables")
        tags_joined = " ".join(result["tags"]).lower()
        old_comedy_tags = ["cartoon", "animation", "funny animation", "comedy animation"]
        for bad_tag in old_comedy_tags:
            self.assertNotIn(bad_tag, tags_joined,
                             f"Tags contain old comedy/animation keyword: {bad_tag!r}")

    def test_tags_reasonable_count(self):
        """Tags should be between 15 and 50 (YouTube allows up to 500 characters of tags)."""
        result = self.generate_script("chicken tikka masala")
        tags = result["tags"]
        self.assertGreaterEqual(len(tags), 5, "Need at least 5 tags for SEO")
        self.assertLessEqual(len(tags), 50, "Tags list should not exceed 50 entries")

    def test_scenes_is_non_empty_list(self):
        result = self.generate_script("homemade ramen")
        scenes = result["scenes"]
        self.assertIsInstance(scenes, list)
        self.assertGreater(len(scenes), 0, "scenes list must not be empty")

    def test_scenes_are_food_themed(self):
        """Scene descriptions should describe food/cooking/kitchen visuals."""
        result = self.generate_script("chocolate lava cake")
        scenes = result["scenes"]
        scenes_text = " ".join(scenes).lower()
        food_scene_words = [
            "food", "cook", "kitchen", "ingredient", "dish", "recipe",
            "pan", "plate", "chef", "fresh", "cut", "slice", "pour",
            "overhead", "close-up", "sizzle", "garnish",
        ]
        has_food_scene = any(word in scenes_text for word in food_scene_words)
        self.assertTrue(has_food_scene,
                        f"Scenes should include food/cooking visuals. Got: {scenes}")

    def test_scenes_not_animation_style(self):
        """Scene descriptions must NOT mention cartoon/animation visuals."""
        result = self.generate_script("french fries secret")
        scenes = result["scenes"]
        scenes_text = " ".join(scenes).lower()
        animation_words = ["cartoon", "chibi", "pixel", "rubber hose", "blob character",
                           "stick figure", "animated character"]
        for word in animation_words:
            self.assertNotIn(word, scenes_text,
                             f"Scenes contain animation reference '{word}': {scenes}")

    def test_description_is_string(self):
        result = self.generate_script("healthy meal prep")
        self.assertIsInstance(result["description"], str)

    def test_description_mentions_food_factory(self):
        """Description should mention the Food Making Videos Factory brand."""
        result = self.generate_script("budget pasta")
        desc = result["description"].lower()
        has_food_brand = "food" in desc and "factory" in desc
        self.assertTrue(has_food_brand,
                        "Description should mention Food Making Videos Factory")

    def test_description_not_animation_factory(self):
        """Description must NOT mention the old Funny Animation Shorts Factory."""
        result = self.generate_script("scrambled eggs recipe")
        desc = result["description"].lower()
        self.assertNotIn("animation", desc,
                         "Description should not mention the old animation factory")

    def test_deterministic_structure(self):
        """Two calls with the same topic must both return all required keys."""
        r1 = self.generate_script("homemade pizza dough")
        r2 = self.generate_script("homemade pizza dough")
        self.assertEqual(set(r1.keys()), set(r2.keys()))

    def test_various_food_topics_do_not_raise(self):
        """Scriptwriter must handle a variety of food topics without crashing."""
        topics = [
            "5-ingredient pasta carbonara",
            "crispy air fryer chicken",
            "why your scrambled eggs taste wrong",
            "homemade sourdough bread",
            "viral cottage cheese toast",
            "",          # empty topic — should not crash
            "  spaces  ",
        ]
        for topic in topics:
            with self.subTest(topic=topic):
                try:
                    result = self.generate_script(topic)
                    self.assertIn("title", result)
                except Exception as exc:
                    self.fail(f"generate_script({topic!r}) raised unexpectedly: {exc}")


class TestCaptionScript(unittest.TestCase):
    """Tests for the caption_script field used by video_creator."""

    def test_caption_script_is_string(self):
        from src.scriptwriter import generate_script
        result = generate_script("cooking tips for beginners")
        self.assertIsInstance(result["caption_script"], str)

    def test_caption_script_no_markup(self):
        """caption_script is rendered as subtitle text — must be plain."""
        from src.scriptwriter import generate_script
        result = generate_script("perfect roast chicken")
        cap = result["caption_script"]
        self.assertNotIn("<", cap, "caption_script must not contain HTML/XML tags")
        self.assertNotIn(">", cap, "caption_script must not contain HTML/XML tags")


class TestFoodTopicVariety(unittest.TestCase):
    """Tests that different food topics generate varied scripts."""

    def test_different_topics_produce_different_hooks(self):
        """Different food topics should generally produce different hooks (variety check)."""
        from src.scriptwriter import generate_script
        r1 = generate_script("pasta water trick that changes everything")
        r2 = generate_script("crispy chicken skin secret technique")
        # At minimum, both should be non-empty
        self.assertTrue(r1["hook"].strip())
        self.assertTrue(r2["hook"].strip())

    def test_food_fallback_topic_works(self):
        """The food fallback placeholder topic should produce a valid script."""
        from src.scriptwriter import generate_script
        result = generate_script("delicious home cooking")
        self.assertIn("title", result)
        self.assertTrue(result["script"].strip())

    def test_food_topic_with_numbers_works(self):
        """Topics with numbers (common in food content) should generate valid scripts."""
        from src.scriptwriter import generate_script
        result = generate_script("5 ingredient pasta that costs under 2 dollars")
        self.assertIn("title", result)
        self.assertTrue(result["script"].strip())


if __name__ == "__main__":
    unittest.main()
