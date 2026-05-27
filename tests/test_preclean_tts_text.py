"""Tests for _preclean_tts_text() in tts.py.

Validates that problematic characters are cleaned before TTS engines see them.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

# _preclean_tts_text uses `import re as _re_tts` at module level in tts.py.
# We can import it directly since it's a pure function with no side effects.
from tts import _preclean_tts_text


class TestPrecleanTtsText(unittest.TestCase):
    """Test suite for TTS text pre-cleaning."""

    # --- Ellipsis handling ---
    def test_smart_ellipsis(self):
        result = _preclean_tts_text("Hello\u2026 World")
        self.assertNotIn("\u2026", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_three_dots(self):
        result = _preclean_tts_text("Wait... what?")
        self.assertNotIn("...", result)
        self.assertIn("Wait", result)
        self.assertIn("what?", result)

    def test_two_dots(self):
        result = _preclean_tts_text("Hmm.. okay")
        self.assertNotIn("..", result)
        self.assertIn("Hmm", result)

    def test_many_dots(self):
        result = _preclean_tts_text("Really......... wow")
        self.assertNotIn("....", result)
        self.assertIn("Really", result)
        self.assertIn("wow", result)

    # --- Quote handling ---
    def test_smart_double_quotes_removed(self):
        result = _preclean_tts_text('\u201cHello\u201d')
        self.assertNotIn("\u201c", result)
        self.assertNotIn("\u201d", result)
        self.assertEqual(result, "Hello")

    def test_smart_single_quotes_to_apostrophe(self):
        result = _preclean_tts_text("It\u2019s-a me!")
        self.assertIn("It's-a me!", result)

    def test_regular_double_quotes_removed(self):
        result = _preclean_tts_text('He said "hello"')
        self.assertNotIn('"', result)
        self.assertIn("He said hello", result)

    # --- Dash handling ---
    def test_em_dash_to_pause(self):
        result = _preclean_tts_text("Mario\u2014the hero")
        self.assertNotIn("\u2014", result)
        self.assertIn("Mario", result)
        self.assertIn("the hero", result)

    def test_en_dash_to_pause(self):
        result = _preclean_tts_text("2024\u20132025")
        self.assertNotIn("\u2013", result)

    # --- Asterisk handling ---
    def test_asterisks_removed(self):
        result = _preclean_tts_text("*laughs* That's funny!")
        self.assertNotIn("*", result)
        self.assertIn("laughs", result)
        self.assertIn("That's funny!", result)

    # --- Artifact cleanup ---
    def test_leading_comma_removed(self):
        result = _preclean_tts_text(", Hello there")
        self.assertTrue(result.startswith("Hello"))

    def test_double_comma_collapsed(self):
        result = _preclean_tts_text("Hello,, World")
        self.assertNotIn(",,", result)

    def test_comma_after_period_removed(self):
        result = _preclean_tts_text("Done. , Next thing")
        self.assertNotIn(". ,", result)

    def test_comma_before_exclamation(self):
        result = _preclean_tts_text("Wahoo, !")
        self.assertNotIn(", !", result)
        self.assertIn("!", result)

    def test_trailing_comma_removed(self):
        result = _preclean_tts_text("Hello world, ")
        self.assertFalse(result.endswith(","))
        self.assertFalse(result.endswith(", "))

    def test_whitespace_collapsed(self):
        result = _preclean_tts_text("Hello    World")
        self.assertNotIn("    ", result)
        self.assertIn("Hello World", result)

    # --- Combined edge cases ---
    def test_ellipsis_before_exclamation(self):
        """'...!' should become '!' not ', !'"""
        result = _preclean_tts_text("Wahoo...!")
        self.assertNotIn(", !", result)
        self.assertIn("!", result)

    def test_empty_string(self):
        result = _preclean_tts_text("")
        self.assertEqual(result, "")

    def test_whitespace_only(self):
        result = _preclean_tts_text("   ")
        self.assertEqual(result, "")

    def test_normal_text_unchanged(self):
        text = "It's-a me, Mario! Let's-a go!"
        result = _preclean_tts_text(text)
        self.assertEqual(result, text)

    def test_complex_mixed(self):
        """Test a realistic LLM output with multiple issues."""
        text = '\u201cWahoo!\u201d *jumps* Let\u2019s-a go\u2026 to the castle\u2014it\u2019s party time!'
        result = _preclean_tts_text(text)
        self.assertNotIn("\u201c", result)
        self.assertNotIn("*", result)
        self.assertNotIn("\u2026", result)
        self.assertNotIn("\u2014", result)
        self.assertIn("Wahoo!", result)
        self.assertIn("Let's-a go", result)
        self.assertIn("it's party time!", result)

    def test_only_punctuation(self):
        """Text that becomes empty after cleaning."""
        result = _preclean_tts_text('..."')
        self.assertEqual(result, "")

    def test_pronunciation_substitutions(self):
        """Pronunciation rules moved to character YAML; preclean no longer substitutes."""
        result = _preclean_tts_text("Wahoo! Whoa! Yippee! Mamma mia! Mama mia! Okie dokie!")
        # preclean only strips formatting; pronunciation handled downstream by YAML rules
        self.assertIn("Wahoo!", result)
        self.assertIn("Okie dokie!", result)

    def test_laughter_substitutions(self):
        """Laughter substitutions moved to YAML rules; preclean preserves text."""
        self.assertEqual(_preclean_tts_text("Ha ha ha"), "Ha ha ha")
        self.assertEqual(_preclean_tts_text("Ha ha"), "Ha ha")


if __name__ == "__main__":
    unittest.main()
