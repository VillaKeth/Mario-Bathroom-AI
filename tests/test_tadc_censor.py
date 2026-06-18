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


def test_pipeline_contract_blocks_and_flags():
    import tadc_censor as tc
    tc.set_enabled(True)
    analyzed = {"display_text": "you little shit", "tts_text": "you little shit", "full_text": "you little shit"}
    d = tc.censor(analyzed["display_text"]); t = tc.censor(analyzed["tts_text"])
    analyzed["display_text"], analyzed["tts_text"] = d.display, t.tts
    censored = (d.count + t.count) > 0
    assert censored is True
    assert "████" in analyzed["display_text"]
    assert "shit" not in analyzed["tts_text"].lower()
    tc.set_enabled(False)
