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


def test_inflected_swears_caught():
    # past-tense / plural / -y forms must bleep too (regression: "fucked" leaked
    # because the word list had "fuck" but \b...\b only matched the exact stem)
    r = tadc_censor.censor("oh shit that is fucked, you bitches are pissed")
    assert r.count == 4
    assert "fucked" not in r.tts.lower()
    assert "bitches" not in r.tts.lower()
    assert "pissed" not in r.tts.lower()


def test_no_false_positive_on_innocent_words():
    # swear stems must not fire inside innocent words (class/passes/glass)
    r = tadc_censor.censor("the class passes the glass case")
    assert r.count == 0
    assert r.display == "the class passes the glass case"


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


def test_character_loader_exposes_franchise(tmp_path):
    import yaml as _yaml
    from shared.character_loader import CharacterLoader
    cdir = tmp_path / "characters" / "testc"
    cdir.mkdir(parents=True)
    (cdir / "character.yaml").write_text(_yaml.dump({
        "identity": {"name": "Testc", "display_name": "Testc", "franchise": "Digital_Circus"},
    }), encoding="utf-8")
    c = CharacterLoader(str(tmp_path / "characters"), "testc")
    assert c.franchise == "digital_circus"   # normalized lower/stripped


def test_character_loader_franchise_defaults_empty(tmp_path):
    import yaml as _yaml
    from shared.character_loader import CharacterLoader
    cdir = tmp_path / "characters" / "plainc"
    cdir.mkdir(parents=True)
    (cdir / "character.yaml").write_text(_yaml.dump({
        "identity": {"name": "Plainc", "display_name": "Plainc"},
    }), encoding="utf-8")
    c = CharacterLoader(str(tmp_path / "characters"), "plainc")
    assert c.franchise == ""


def test_censor_analyzed_blocks_strips_and_flags():
    analyzed = {"display_text": "you little shit", "tts_text": "you little shit", "full_text": "you little shit"}
    censored = tadc_censor.censor_analyzed(analyzed)
    assert censored is True
    assert "████" in analyzed["display_text"]
    assert "████" in analyzed["full_text"]
    assert "shit" not in analyzed["tts_text"].lower()


def test_censor_analyzed_clean_text_no_flag():
    analyzed = {"display_text": "hello there", "tts_text": "hello there", "full_text": "hello there"}
    assert tadc_censor.censor_analyzed(analyzed) is False
    assert analyzed["display_text"] == "hello there"
    assert analyzed["tts_text"] == "hello there"


def test_adc_pipeline_order_swear_becomes_block_not_redaction():
    # ADC chars set safety.enabled=false so swears survive filter_response and reach
    # the TADC styler (block). With safety ON they would be pre-redacted to **** and
    # the censor would never fire -- regression guard for that ordering bug.
    import safety_filter
    try:
        safety_filter.set_safety_config(enabled=False, block_slurs=True)
        filtered = safety_filter.filter_response("oh shit")
        assert "shit" in filtered
        analyzed = {"display_text": filtered, "tts_text": filtered}
        assert tadc_censor.censor_analyzed(analyzed) is True
        assert "████" in analyzed["display_text"]
        assert "****" not in analyzed["display_text"]
    finally:
        safety_filter.set_safety_config(enabled=True, block_slurs=True)


def test_safety_on_redacts_swear_before_tadc_would_see_it():
    # The other direction: safety ON pre-redacts to **** so an ADC char must NOT
    # leave safety on, or the TADC styling never happens.
    import safety_filter
    try:
        safety_filter.set_safety_config(enabled=True, block_slurs=True)
        filtered = safety_filter.filter_response("oh shit")
        assert "shit" not in filtered and "****" in filtered
    finally:
        safety_filter.set_safety_config(enabled=True, block_slurs=True)
