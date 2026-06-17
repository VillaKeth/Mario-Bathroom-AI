"""The wizard's sprite_prompts.txt must be parseable by the mcp_chatgpt batch."""
import os
import re
import tempfile

import yaml

from character_creator.sprite_generator import build_sprite_prompts_text

# The exact block regex mcp_chatgpt/batch_sprites.py uses to parse the file.
_BLOCK = re.compile(r"\[(\d+)\]\s+(\S+)\s*\n-+\n(.+?)(?=\n\[\d+\]|\Z)", re.S)


def _make_char(tmp, visuals_extra=None, identity=None):
    visuals = {
        "visual_description": "a small round blue robot with big eyes",
        "art_style": "3d_figurine",
        "emotion_sprite_map": {"happy": "positive/happy", "sad": "negative/sad",
                               "zany_custom": "reactions/zany_custom"},
        "state_sprite_map": {"idle": "neutral/idle",
                             "talking": ["speech/talking", "speech/talking_excited"]},
    }
    visuals.update(visuals_extra or {})
    y = {"identity": identity or {"name": "Testy", "display_name": "Testy Bot"},
         "visuals": visuals}
    d = os.path.join(tmp, "testy")
    os.makedirs(d)
    with open(os.path.join(d, "character.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(y, f, allow_unicode=True)
    return d


def test_output_parses_with_batch_regex():
    with tempfile.TemporaryDirectory() as tmp:
        d = _make_char(tmp)
        text, n = build_sprite_prompts_text(d)
        blocks = _BLOCK.findall(text)
        # 6 unique paths: positive/happy, negative/sad, reactions/zany_custom,
        # neutral/idle, speech/talking, speech/talking_excited
        assert n == 6
        assert len(blocks) == n
        # indices are sequential 1..n
        assert [int(b[0]) for b in blocks] == list(range(1, n + 1))


def test_paths_and_prompt_content():
    with tempfile.TemporaryDirectory() as tmp:
        d = _make_char(tmp)
        text, _ = build_sprite_prompts_text(d)
        for _idx, path, prompt in _BLOCK.findall(text):
            assert path.startswith("sprites/") and path.endswith(".png")
            assert "a small round blue robot" in prompt        # visual_description woven in
            assert "figurine" in prompt                         # art-style suffix applied
            assert "head to toe" in prompt                      # framing suffix applied


def test_custom_emotion_key_gets_fallback_direction():
    with tempfile.TemporaryDirectory() as tmp:
        d = _make_char(tmp)
        text, _ = build_sprite_prompts_text(d)
        # the non-canonical key 'zany_custom' still yields a usable pose line
        block = [b for b in _BLOCK.findall(text) if b[1] == "sprites/reactions/zany_custom.png"]
        assert block and "zany custom" in block[0][2]


def test_falls_back_to_identity_when_no_visual_description():
    with tempfile.TemporaryDirectory() as tmp:
        d = _make_char(tmp, visuals_extra={"visual_description": ""},
                       identity={"name": "Glorp", "display_name": "Glorp",
                                 "description": "a friendly alien blob"})
        text, _ = build_sprite_prompts_text(d)
        assert "friendly alien blob" in text
