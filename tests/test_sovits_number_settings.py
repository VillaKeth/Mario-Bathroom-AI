"""Numbers and prose want opposite inference settings, so stop shipping one set.

The server has always sent cut5 + tight sampling for every line. cut5 splits at
EVERY punctuation mark, commas included, and each fragment is generated
independently with a 0.3s gap dropped between them.

For a countdown that is exactly the cure: "Five, four, three, two, one" becomes
five separate renders instead of one slurred blur. For prose it is the disease:
"Hey there, welcome to the party" gets chopped at the comma, the two halves get
unrelated prosody, and a pause lands in the middle of a breath.

So route on content: number-dense text keeps cut5 and the tight sampling, plain
speech gets sentence-level splitting and the looser sampling that sounds better.

Detection runs on the CLEANED text, because clean_text_for_tts() has already
spelled digits out into words by then -- "27" is "twenty seven" by the time the
model sees it, and a digit check alone would miss every converted number.
"""
import pytest

from server import gpt_sovits_server as gs


# --- which preset does a line get? -----------------------------------------

def test_countdown_gets_the_number_preset():
    """The original complaint: "slurs digits together"."""
    p = gs.infer_params_for("Let me count us down. Five, four, three, two, one.")
    assert p["text_split_method"] == "cut5"


def test_plain_prose_does_not_get_chopped_at_commas():
    p = gs.infer_params_for("Hey there, welcome to the party. Glad you could make it.")
    assert p["text_split_method"] != "cut5", (
        "cut5 splits at the comma, which is the weird pacing the user reported")


def test_one_lone_number_is_still_prose():
    """A single number is not slurred against anything, so don't wreck the line.

    "four" rendering badly on its own is a training-data gap -- it fails on the
    old and new models alike -- and no split method fixes it. Chopping the whole
    sentence at its commas to chase it costs more than it buys.
    """
    p = gs.infer_params_for("I need four volunteers for this, if you are willing.")
    assert p["text_split_method"] != "cut5"


def test_bare_countdown_tick_gets_the_number_preset():
    """Game countdowns arrive one word at a time, so adjacency never sees them.

    game_handlers speaks "Three!", then "Two!", then "One!" as separate
    utterances. Those bare ticks are the exact text the voice garbles worst.
    """
    for tick in ("Three!", "Two!", "One!", "Ten!"):
        assert gs.infer_params_for(tick)["top_k"] == gs.PARAMS_NUMBERS["top_k"], tick


def test_a_number_word_in_a_long_sentence_is_still_prose():
    """The short-utterance rule must not swallow ordinary sentences."""
    p = gs.infer_params_for("You are the one person here I actually wanted to see.")
    assert p["text_split_method"] != "cut5"


def test_compound_number_gets_the_number_preset():
    """"twenty seven" is two adjacent number words -- the slurring case."""
    assert gs.infer_params_for(
        "There are twenty seven people here tonight.")["text_split_method"] == "cut5"


def test_spoken_time_gets_the_number_preset():
    assert gs.infer_params_for(
        "It is eleven forty five already.")["text_split_method"] == "cut5"


def test_surviving_digits_get_the_number_preset():
    """Anything clean_text_for_tts could not spell out (>999, decimals, codes)."""
    assert gs.infer_params_for(
        "The code is 4815.")["text_split_method"] == "cut5"


def test_and_does_not_break_a_number_run():
    assert gs.infer_params_for(
        "One hundred and five.")["text_split_method"] == "cut5"


# --- the presets themselves -------------------------------------------------

def test_the_routes_differ_in_splitting_and_not_in_sampling():
    """The prose route briefly sampled flatter, and that was a mistake.

    temp 0.70 / top_k 8 came from the checkpoint-comparison rig, where sampling
    was deliberately flattened so the checkpoint would be the only moving part.
    Shipping those values made prose duller on a line where the split was
    identical either way. Splitting is the axis that should differ.
    """
    prose = gs.infer_params_for("Take a deep breath, you are going to be fine.")
    nums = gs.infer_params_for("Ten, nine, eight, seven, six.")
    assert prose["text_split_method"] != nums["text_split_method"]
    for knob in ("top_k", "top_p", "temperature", "repetition_penalty"):
        assert prose[knob] == nums[knob], knob


def test_every_preset_is_a_complete_request():
    """A half-filled preset silently inherits upstream defaults. Pin all of it."""
    need = {"text_split_method", "top_k", "top_p", "temperature", "repetition_penalty"}
    for text in ("Five, four, three.", "Good to see you again."):
        assert need <= set(gs.infer_params_for(text)), text


def test_presets_are_not_shared_mutable_state():
    """Callers merge into the returned dict; a shared one would poison the next."""
    a = gs.infer_params_for("Hello there.")
    a["temperature"] = 99
    assert gs.infer_params_for("Hello there.")["temperature"] != 99


# --- the wiring, not just the helper ---------------------------------------

class _FakePipeline:
    """Captures the request synthesize() builds and returns 1s of silence."""

    def __init__(self):
        self.req = None

    def run(self, req):
        import numpy as np
        self.req = dict(req)
        yield 32000, np.zeros(32000, dtype=np.float32)


@pytest.mark.parametrize("text,expect", [
    ("Five, four, three, two, one.", "cut5"),
    ("Hey there, welcome to the party.", "cut2"),
])
def test_synthesize_actually_sends_the_chosen_preset(text, expect, tmp_path, monkeypatch):
    import wave

    ref = tmp_path / "ref.wav"
    with wave.open(str(ref), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(32000)
        w.writeframes(b"\x00\x00" * 32000)

    monkeypatch.setattr(gs, "OUTPUT_DIR", str(tmp_path))
    pipe = _FakePipeline()
    gs.synthesize(pipe, text, ref_audio=str(ref), prompt_text="hi")

    assert pipe.req is not None, "pipeline was never run"
    assert pipe.req["text_split_method"] == expect
