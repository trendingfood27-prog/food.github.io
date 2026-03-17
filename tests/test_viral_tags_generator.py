"""
tests/test_viral_tags_generator.py — Unit tests for src/viral_tags_generator.py

Tests the multi-tier tagging system with no external API calls.
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


class TestGenerateViralTags(unittest.TestCase):
    """Tests for viral_tags_generator.generate_viral_tags()."""

    def setUp(self):
        from src.viral_tags_generator import generate_viral_tags
        self.generate_viral_tags = generate_viral_tags

    def test_returns_list(self):
        tags = self.generate_viral_tags("pasta carbonara")
        self.assertIsInstance(tags, list)

    def test_returns_30_to_50_tags(self):
        tags = self.generate_viral_tags("crispy chicken recipe")
        self.assertGreaterEqual(len(tags), 30, f"Expected ≥30 tags, got {len(tags)}")
        self.assertLessEqual(len(tags), 50, f"Expected ≤50 tags, got {len(tags)}")

    def test_all_tags_are_strings(self):
        tags = self.generate_viral_tags("salmon recipe")
        self.assertTrue(all(isinstance(t, str) for t in tags),
                        "All tags must be strings")

    def test_no_empty_tags(self):
        tags = self.generate_viral_tags("pasta recipe")
        self.assertTrue(all(t.strip() for t in tags), "No tag should be empty or whitespace")

    def test_no_duplicate_tags(self):
        tags = self.generate_viral_tags("chicken curry")
        lower_tags = [t.lower() for t in tags]
        self.assertEqual(len(lower_tags), len(set(lower_tags)), "Tags should be deduplicated")

    def test_broad_food_tags_included(self):
        """Tier-1 broad tags like 'food' and 'recipe' should always be included."""
        tags = self.generate_viral_tags("homemade bread")
        tags_lower = [t.lower() for t in tags]
        self.assertIn("food", tags_lower, "Broad tag 'food' should be present")
        self.assertIn("recipe", tags_lower, "Broad tag 'recipe' should be present")

    def test_ingredient_specific_tags_included(self):
        """Niche tier: pasta topic should include pasta-specific tags."""
        tags = self.generate_viral_tags("pasta carbonara")
        tags_lower_joined = " ".join(t.lower() for t in tags)
        self.assertIn("pasta", tags_lower_joined, "Pasta topic should include pasta-related tags")

    def test_trending_format_tags_included(self):
        """Tier-3 trending format tags should be present."""
        tags = self.generate_viral_tags("air fryer chicken wings")
        tags_lower = [t.lower() for t in tags]
        trending_found = any("quick" in t or "easy" in t or "airfryer" in t
                             or "viral" in t or "shorts" in t for t in tags_lower)
        self.assertTrue(trending_found, "Should include trending format tags")

    def test_respects_target_count(self):
        """generate_viral_tags should respect custom target_count (clamped to 30-50)."""
        tags_30 = self.generate_viral_tags("steak recipe", target_count=30)
        tags_50 = self.generate_viral_tags("steak recipe", target_count=50)
        self.assertLessEqual(len(tags_30), 30)
        self.assertLessEqual(len(tags_50), 50)

    def test_existing_tags_merged(self):
        """Existing tags should be incorporated into the result."""
        my_unique_tag = "myveryuniquetagxyz"
        tags = self.generate_viral_tags("pizza recipe", existing_tags=[my_unique_tag])
        self.assertIn(my_unique_tag, tags, "Existing tags should be merged into result")

    def test_no_tags_with_hash_prefix(self):
        """YouTube tags should not start with # (that's for descriptions/comments)."""
        tags = self.generate_viral_tags("vegetarian curry")
        for tag in tags:
            self.assertFalse(tag.startswith("#"), f"Tag should not start with #: {tag!r}")

    def test_various_food_topics_do_not_raise(self):
        """Various food topics should all generate tags without crashing."""
        topics = [
            "spaghetti carbonara",
            "crispy air fryer chicken",
            "chocolate lava cake",
            "biryani recipe",
            "vegan pad thai",
            "",
            "   ",
        ]
        for topic in topics:
            with self.subTest(topic=topic):
                try:
                    tags = self.generate_viral_tags(topic)
                    self.assertIsInstance(tags, list)
                except Exception as exc:
                    self.fail(f"generate_viral_tags({topic!r}) raised: {exc}")


class TestGenerateViralDescription(unittest.TestCase):
    """Tests for viral_tags_generator.generate_viral_description()."""

    def setUp(self):
        from src.viral_tags_generator import generate_viral_description
        self.generate_viral_description = generate_viral_description

    def test_returns_string(self):
        desc = self.generate_viral_description("pasta", "Best Pasta Recipe", ["pasta", "recipe"])
        self.assertIsInstance(desc, str)

    def test_description_is_non_empty(self):
        desc = self.generate_viral_description("pasta", "Best Pasta Recipe", ["pasta"])
        self.assertTrue(desc.strip())

    def test_contains_topic_keyword(self):
        desc = self.generate_viral_description("chicken tikka", "Best Chicken", ["chicken"])
        self.assertIn("chicken tikka", desc.lower(), "Description should mention the topic")

    def test_contains_subscribe_cta(self):
        desc = self.generate_viral_description("pasta", "Pasta Recipe", ["pasta", "food"])
        desc_lower = desc.lower()
        has_cta = any(word in desc_lower for word in ["subscribe", "like", "follow", "comment"])
        self.assertTrue(has_cta, "Description should include an engagement CTA")

    def test_contains_food_factory_brand(self):
        """Description should mention the Food Making Videos Factory brand."""
        desc = self.generate_viral_description("steak", "Perfect Steak", ["steak"])
        self.assertIn("food", desc.lower())
        self.assertIn("factory", desc.lower())

    def test_with_steps_includes_timestamps(self):
        steps = ["Prep ingredients", "Heat the pan", "Add protein", "Season generously"]
        desc = self.generate_viral_description("chicken", "Chicken Recipe", ["chicken"],
                                               steps=steps)
        self.assertIn("TIMESTAMPS", desc.upper(), "Description with steps should include timestamps")

    def test_with_cook_time_includes_time(self):
        desc = self.generate_viral_description("pasta", "Pasta Recipe", ["pasta"],
                                               cook_time_minutes=15)
        self.assertIn("15", desc, "Description should mention cook time")

    def test_with_tips_includes_tips(self):
        tips = ["Always salt your pasta water", "Use fresh garlic for best flavour"]
        desc = self.generate_viral_description("pasta", "Pasta Recipe", ["pasta"], tips=tips)
        self.assertIn("TIP", desc.upper(), "Description with tips should include a tips section")


class TestCleanTag(unittest.TestCase):
    """Tests for viral_tags_generator._clean_tag()."""

    def test_strips_hash_prefix(self):
        from src.viral_tags_generator import _clean_tag
        self.assertEqual(_clean_tag("#pasta"), "pasta")

    def test_lowercases(self):
        from src.viral_tags_generator import _clean_tag
        result = _clean_tag("PastaRecipe")
        self.assertEqual(result, result.lower())

    def test_removes_special_chars(self):
        from src.viral_tags_generator import _clean_tag
        result = _clean_tag("pasta!@#$")
        self.assertNotIn("!", result)
        self.assertNotIn("@", result)

    def test_empty_tag_returns_empty_string(self):
        from src.viral_tags_generator import _clean_tag
        self.assertEqual(_clean_tag(""), "")
        self.assertEqual(_clean_tag("  "), "")

    def test_single_char_tag_rejected(self):
        from src.viral_tags_generator import _clean_tag
        self.assertEqual(_clean_tag("a"), "")


if __name__ == "__main__":
    unittest.main()
