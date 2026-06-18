import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import tadc_censor


def test_clean_text_unchanged():
    r = tadc_censor.censor("hello there friend")
    assert r.display == "hello there friend"
    assert r.tts == "hello there friend"
    assert r.count == 0


def test_single_swear_blocked_in_display_and_removed_from_tts():
    r = tadc_censor.censor("oh fuck this")
    assert r.count == 1
    assert "████" in r.display
    assert "fuck" not in r.display.lower()
    assert "fuck" not in r.tts.lower()


def test_multiple_swears_counted():
    r = tadc_censor.censor("shit, that is fucking great")
    assert r.count == 2
    assert r.display.count("████") == 2


def test_compound_word_blocked_whole():
    r = tadc_censor.censor("that is bullshit")
    assert r.count == 1
    assert r.display == "that is ████"


def test_case_insensitive():
    assert tadc_censor.censor("FUCK").count == 1


def test_empty_text():
    r = tadc_censor.censor("")
    assert r.count == 0 and r.display == "" and r.tts == ""


def test_enabled_gate_defaults_off_and_toggles():
    tadc_censor.set_enabled(False)
    assert tadc_censor.is_enabled() is False
    tadc_censor.set_enabled(True)
    assert tadc_censor.is_enabled() is True
    tadc_censor.set_enabled(False)  # reset for other tests


def test_tts_sentence_leading_swear_has_no_comma_artifacts():
    r = tadc_censor.censor("fuck, that was wild")
    assert r.tts == "that was wild"
    assert ", ," not in r.tts and not r.tts.startswith(",")


def test_tts_adjacent_swears_collapse_to_empty():
    r = tadc_censor.censor("shit fuck")
    assert r.count == 2
    assert r.tts == ""


def test_censor_runs_regardless_of_enabled_flag():
    # censor() does not gate on _ENABLED; the caller checks is_enabled() first.
    tadc_censor.set_enabled(False)
    assert tadc_censor.censor("fuck").count == 1
