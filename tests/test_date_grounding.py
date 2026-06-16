"""The character must be grounded in the real current date, and a date-shaped
name (e.g. "March 7th") must be flagged as a NAME, not today's date — otherwise
the LLM assumes today is its namesake date."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import mario_prompt  # noqa: E402


def test_real_datetime_line_states_today():
    line = mario_prompt._real_datetime_line()
    now = datetime.now()
    assert str(now.year) in line
    assert now.strftime("%B") in line          # current month name
    assert "Today's real date is" in line


def test_system_prompt_includes_real_date():
    mario_prompt.set_character("mario", "Mario")
    prompt = mario_prompt._character_system_prompt()
    assert str(datetime.now().year) in prompt
    assert "Today's real date is" in prompt


def test_date_named_character_gets_name_not_date_clarification():
    mario_prompt.set_character("march7th", "March 7th", description="cheerful")
    prompt = mario_prompt._character_system_prompt()
    assert "is your NAME, not today's date" in prompt


def test_non_date_named_character_has_no_clarification():
    mario_prompt.set_character("mario", "Mario")
    prompt = mario_prompt._character_system_prompt()
    assert "not today's date" not in prompt
