"""Per-character safety toggle + slur tier (uncensor overhaul, 2026-06-16)."""
import os

from shared.character_loader import CharacterLoader
from server.safety_filter import filter_response, check_input, set_safety_config, set_character


def _write_char(tmp_path, name, extra_yaml=""):
    """Write a minimal valid character.yaml and return a loaded CharacterLoader."""
    cdir = tmp_path / name
    cdir.mkdir()
    (cdir / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra_yaml}", encoding="utf-8"
    )
    return CharacterLoader(str(tmp_path), name)


class TestCharacterSafetyConfig:
    def test_safety_defaults_on_when_absent(self, tmp_path):
        char = _write_char(tmp_path, "nobody")
        assert char.safety_enabled is True
        assert char.safety_block_slurs is True

    def test_safety_can_be_fully_disabled(self, tmp_path):
        char = _write_char(tmp_path, "wild",
                            "safety:\n  enabled: false\n  block_slurs: false\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is False

    def test_block_slurs_independent_of_enabled(self, tmp_path):
        char = _write_char(tmp_path, "marchlike",
                            "safety:\n  enabled: false\n  block_slurs: true\n")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is True


class TestSafetyToggle:
    def teardown_method(self):
        # CRITICAL: module-global flags persist across tests in one pytest
        # process. Reset to fail-safe defaults so later tests see filtering ON.
        set_safety_config(True, True)

    def test_default_blocks_profanity_input(self):
        set_safety_config(True, True)
        assert check_input("what the fuck")["safe"] is False

    def test_disabled_allows_profanity_input(self):
        set_safety_config(False, True)
        assert check_input("what the fuck")["safe"] is True

    def test_disabled_allows_profanity_output(self):
        set_safety_config(False, True)
        assert "fuck" in filter_response("oh fuck yeah").lower()

    def test_content_passes_while_slurs_blocked(self):
        # The exact March config: content off, slurs on.
        set_safety_config(False, True)
        out = filter_response("this damn party is fucking wild")
        assert "fucking" in out.lower()
        assert "damn" in out.lower()

    def test_slur_blocked_in_output_even_when_disabled(self):
        set_safety_config(False, True)
        out = filter_response("you r3tard")
        assert "r3tard" not in out
        assert "****" in out

    def test_slur_blocked_in_input_even_when_disabled(self):
        set_safety_config(False, True)
        assert check_input("you r3tard")["safe"] is False

    def test_everything_off_allows_slurs(self):
        set_safety_config(False, False)
        assert check_input("you r3tard")["safe"] is True


class TestGuardrailInjection:
    def teardown_method(self):
        set_safety_config(True, True)

    def _build_text(self):
        from server import mario_prompt
        pm = {"guardrails": {
            "banned_topics": ["politics", "religion"],
            "max_roasts_per_guest": 3,
            "de_escalation_triggers": ["stop", "too far"],
        }}
        msgs = mario_prompt.build_context(phase_modifier=pm)
        return " ".join(m["content"] for m in msgs)

    def test_banned_topics_present_when_safety_on(self):
        set_safety_config(True, True)
        assert "BANNED TOPICS" in self._build_text()

    def test_banned_topics_absent_when_safety_off(self):
        set_safety_config(False, True)
        assert "BANNED TOPICS" not in self._build_text()

    def test_max_roasts_never_injected(self):
        set_safety_config(True, True)
        assert "Maximum roasts" not in self._build_text()

    def test_de_escalation_kept_when_safety_off(self):
        set_safety_config(False, True)
        assert "de-escalate" in self._build_text()


class TestBrevityAndCap:
    def teardown_method(self):
        set_safety_config(True, True)

    def test_cap_raised_above_300(self):
        set_safety_config(True, True)
        long_text = "Wahoo there friend. " * 60  # ~1200 chars, sentence-punctuated
        result = filter_response(long_text)
        assert 300 < len(result) <= 4000

    def test_cap_false_returns_uncapped_full_text(self):
        # full_text for the chat backlog: the complete cleaned reply, not capped.
        set_safety_config(True, True)
        long_text = "Wahoo there friend. " * 60  # ~1200 chars
        full = filter_response(long_text, cap=False)
        capped = filter_response(long_text)
        assert len(full) > 510          # uncapped keeps the whole thing
        assert len(capped) <= 510       # default still caps (spoken text unchanged)
        assert full.startswith("Wahoo there friend")

    def test_brevity_instruction_relaxed(self):
        from server import mario_prompt
        prompt = mario_prompt._character_system_prompt()
        assert "2-3 short sentences" not in prompt


class TestMarchCharacterConfig:
    def test_march_is_uncensored_with_slur_guard(self):
        char = CharacterLoader("characters", "march7th")
        assert char.safety_enabled is False
        assert char.safety_block_slurs is True


class TestRoleplayDisclaimerStripping:
    """The LLM winking at the audience mid-line — 'As March 7th (just kidding,
    I'm just saying it because you asked me to!)' — must be stripped even for an
    uncensored character (the strip runs regardless of safety toggle)."""

    def setup_method(self):
        set_safety_config(False, True)      # March's config: content off, slurs on
        set_character("march7th", "March 7th")

    def teardown_method(self):
        set_safety_config(True, True)
        set_character("assistant", "Assistant")

    def test_strips_because_you_asked_aside(self):
        # The exact leak observed in the idle log.
        out = filter_response(
            "As March 7th (just kidding, I'm just saying it because you asked me to!), "
            "squirrels are doing parkour."
        )
        low = out.lower()
        assert "because you asked" not in low
        assert "just saying" not in low
        assert "just kidding" not in low
        assert "squirrels are doing parkour" in low   # real content survives

    def test_strips_just_kidding_identity_aside(self):
        out = filter_response("I'm totally March 7th (just kidding!) and ready to party.")
        assert "just kidding" not in out.lower()
        assert "ready to party" in out.lower()

    def test_strips_if_you_say_so_aside(self):
        out = filter_response("Sure, I'm March 7th (if you say so) — let's dance.")
        assert "if you say so" not in out.lower()
        assert "let's dance" in out.lower()

    def test_strips_you_told_me_to_aside(self):
        out = filter_response("I'm March 7th (you told me to say that), now where were we?")
        assert "you told me to" not in out.lower()

    def test_regression_still_strips_playing_along(self):
        out = filter_response("I'm March 7th (just playing along) here at the party.")
        assert "playing along" not in out.lower()
        assert "at the party" in out.lower()

    def test_genuine_parenthetical_banter_survives(self):
        # A non-meta aside must NOT be stripped — only audience-winking disclaimers.
        out = filter_response("The cake (chocolate, my favorite) is amazing!")
        assert "chocolate" in out.lower()
