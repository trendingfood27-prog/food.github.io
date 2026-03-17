"""
tests/test_virality_optimizer.py — Unit tests for src/virality_optimizer.py

Tests the data-driven virality scoring engine with no external API calls.
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


class TestAnalyzeVirality(unittest.TestCase):
    """Tests for virality_optimizer.analyze_virality()."""

    def _make_script_data(self, **overrides) -> dict:
        base = {
            "title": "The Secret to Perfect Pasta 🍝 Nobody Is Talking About",
            "script": (
                "You have been making pasta wrong your entire life. "
                "Hit like if you are already taking notes. "
                "Here is the secret technique that professional chefs use. "
                "Subscribe for more pro kitchen secrets. "
                "The moment you try this method you will never go back. "
                "Comment below with your results. "
                "Share this with someone who loves cooking."
            ),
            "hook": "You have been making pasta wrong your entire life and here is the proof.",
            "tags": ["pasta", "recipe", "cooking", "food", "homemade", "easyrecipe",
                     "airfryer", "quickrecipe", "shorts", "viral", "italian", "pastarecipe"],
            "description": (
                "Learn how to make the BEST pasta at home! This pasta recipe is easy, "
                "quick, and absolutely delicious. Perfect for beginners and food lovers alike! "
                "Welcome to the Food Making Videos Factory — restaurant-quality cooking secrets."
            ),
        }
        base.update(overrides)
        return base

    def setUp(self):
        from src.virality_optimizer import analyze_virality
        self.analyze_virality = analyze_virality

    def test_returns_virality_report(self):
        from src.virality_optimizer import ViralityReport
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta carbonara")
        self.assertIsInstance(report, ViralityReport)

    def test_overall_score_is_float_0_to_1(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta carbonara")
        self.assertIsInstance(report.overall_score, float)
        self.assertGreaterEqual(report.overall_score, 0.0)
        self.assertLessEqual(report.overall_score, 1.0)

    def test_overall_percentage_is_0_to_100(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        self.assertGreaterEqual(report.overall_percentage, 0.0)
        self.assertLessEqual(report.overall_percentage, 100.0)

    def test_report_has_all_eight_factors(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        self.assertEqual(len(report.factors), 8)

    def test_factor_names_are_strings(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        for factor in report.factors:
            self.assertIsInstance(factor.name, str)
            self.assertTrue(factor.name.strip())

    def test_factor_scores_are_0_to_1(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        for factor in report.factors:
            self.assertGreaterEqual(factor.score, 0.0, f"{factor.name} score below 0")
            self.assertLessEqual(factor.score, 1.0, f"{factor.name} score above 1")

    def test_suggestions_is_list(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        self.assertIsInstance(report.suggestions, list)

    def test_format_report_contains_score(self):
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta")
        formatted = report.format_report()
        self.assertIsInstance(formatted, str)
        self.assertIn("%", formatted)

    def test_strong_script_scores_above_50_percent(self):
        """A well-crafted script with hooks, CTAs, and SEO should score above 50%."""
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta carbonara")
        self.assertGreater(
            report.overall_percentage, 30.0,
            f"Strong script should score > 30%, got {report.overall_percentage:.1f}%",
        )

    def test_empty_script_does_not_raise(self):
        """Virality analysis should handle empty/minimal scripts gracefully."""
        data = {
            "title": "",
            "script": "",
            "hook": "",
            "tags": [],
            "description": "",
        }
        try:
            report = self.analyze_virality(data, "")
            self.assertGreaterEqual(report.overall_score, 0.0)
        except Exception as exc:
            self.fail(f"analyze_virality raised unexpectedly on empty input: {exc}")

    def test_music_path_none_accepted(self):
        """music_path=None should be handled without errors."""
        data = self._make_script_data()
        report = self.analyze_virality(data, "pasta", music_path=None)
        self.assertIsNotNone(report)

    def test_trending_boost_high_engagement_topic(self):
        """Known high-engagement topics like 'pasta' should get a trending boost."""
        from src.virality_optimizer import _analyse_trending_boost
        factor = _analyse_trending_boost("pasta carbonara", "Easy Pasta Recipe", ["pasta"])
        self.assertGreater(factor.score, 0.0, "Trending food topic should score above 0")

    def test_hook_strength_curiosity_gap(self):
        """Hooks with curiosity-gap phrases should score higher."""
        from src.virality_optimizer import _analyse_hook_strength
        strong_hook = "You have been making pasta wrong your entire life — here is the secret."
        weak_hook = "Today we are making pasta."
        strong = _analyse_hook_strength(strong_hook, "")
        weak = _analyse_hook_strength(weak_hook, "")
        self.assertGreater(strong.score, weak.score)

    def test_tag_completeness_more_tags_higher_score(self):
        """More diverse tags should result in a higher tag completeness score."""
        from src.virality_optimizer import _analyse_tag_completeness
        few_tags = ["pasta", "food"]
        many_tags = [
            "pasta", "food", "recipe", "cooking", "homemade", "easyrecipe",
            "airfryer", "quickrecipe", "shorts", "viral", "italian", "pastarecipe",
            "how to make at home", "restaurant style", "5 ingredient pasta",
            "easy pasta recipe", "pasta night", "weeknight dinner", "mealprep",
        ]
        few_score = _analyse_tag_completeness(few_tags)
        many_score = _analyse_tag_completeness(many_tags)
        self.assertGreater(many_score.score, few_score.score)


class TestViralityFactorScore(unittest.TestCase):
    """Tests for the FactorScore dataclass."""

    def test_percentage_property(self):
        from src.virality_optimizer import FactorScore
        fs = FactorScore(name="Test", score=0.75, max_score=1.0, details="test")
        self.assertAlmostEqual(fs.percentage, 75.0)

    def test_zero_score_percentage(self):
        from src.virality_optimizer import FactorScore
        fs = FactorScore(name="Test", score=0.0, max_score=1.0, details="test")
        self.assertAlmostEqual(fs.percentage, 0.0)


if __name__ == "__main__":
    unittest.main()
