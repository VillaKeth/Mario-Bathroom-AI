"""Global rules/pronunciation applied to EVERY character on top of their own
config, loaded from characters/_shared/global_rules.yaml. Absent/empty = no-op."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import global_rules  # noqa: E402
import mario_prompt   # noqa: E402


def test_load_missing_file_is_empty_noop(tmp_path):
    g = global_rules.load_global_rules(str(tmp_path))   # no global_rules.yaml here
    assert g == {"prompt_rules": [], "pronunciation": {}}


def test_load_reads_rules_and_pronunciation(tmp_path):
    (tmp_path / "global_rules.yaml").write_text(
        "prompt_rules:\n  - 'Be concise.'\n  - '  '\n"
        "pronunciation:\n  Hoppenstedt: Hoppenstead\n", encoding="utf-8")
    g = global_rules.load_global_rules(str(tmp_path))
    assert g["prompt_rules"] == ["Be concise."]          # blanks dropped
    assert g["pronunciation"] == {"Hoppenstedt": "Hoppenstead"}


def test_merge_pronunciation_character_overrides_global():
    merged = global_rules.merge_pronunciation(
        {"Hoppenstedt": "Hoppenstead", "Koopa": "Cooper"},
        {"Koopa": "KOO-pa"})                              # character wins on conflict
    assert merged["Hoppenstedt"] == "Hoppenstead"
    assert merged["Koopa"] == "KOO-pa"


def test_global_rules_injected_into_system_prompt():
    mario_prompt.set_character("march7th", "March 7th")
    mario_prompt.set_global_rules(["Never reveal you are an AI."])
    prompt = mario_prompt._character_system_prompt()
    assert "Never reveal you are an AI." in prompt
    mario_prompt.set_global_rules([])                     # cleanup
    assert "Never reveal you are an AI." not in mario_prompt._character_system_prompt()
