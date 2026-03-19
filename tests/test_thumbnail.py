"""Focused tests for src/thumbnail.py helper logic."""

import unittest


class TestTruncateTitleLines(unittest.TestCase):
    """Tests for src.thumbnail._truncate_title_lines()."""

    def setUp(self):
        import src.thumbnail as th
        self.th = th

    def test_keeps_short_titles_unchanged(self):
        lines = ["ONE", "TWO"]
        self.assertEqual(self.th._truncate_title_lines(lines, max_lines=3), lines)

    def test_truncates_to_max_lines_and_appends_ellipsis(self):
        lines = ["ONE", "TWO", "THREE", "FOUR"]
        self.assertEqual(
            self.th._truncate_title_lines(lines, max_lines=3),
            ["ONE", "TWO", "THREE..."],
        )

    def test_does_not_duplicate_ellipsis(self):
        lines = ["ONE", "TWO", "THREE...", "FOUR"]
        self.assertEqual(
            self.th._truncate_title_lines(lines, max_lines=3),
            ["ONE", "TWO", "THREE..."],
        )
