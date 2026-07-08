import os, yaml
from server.joke_engine import load_freaky_jokes

RUDI = os.path.join("characters", "rudi")

def test_rudi_freaky_file_exists_and_loads():
    fp = load_freaky_jokes(RUDI)
    assert len(fp["bravado"]) >= 120, f"bravado too small: {len(fp['bravado'])}"
    assert len(fp["explicit"]) >= 40, f"explicit too small: {len(fp['explicit'])}"

def test_rudi_freaky_is_tts_safe():
    fp = load_freaky_jokes(RUDI)
    all_lines = fp["bravado"] + fp["explicit"]
    for ln in all_lines:
        assert "..." not in ln and "…" not in ln, f"ellipsis: {ln}"
        assert "*" not in ln, f"asterisk: {ln}"
        for w in ln.split():
            stripped = "".join(ch for ch in w if ch.isalpha())
            assert not (len(stripped) > 5 and stripped.isupper()), f"ALLCAPS: {ln}"

def test_rudi_freaky_no_duplicates():
    fp = load_freaky_jokes(RUDI)
    all_lines = [l.strip().lower() for l in fp["bravado"] + fp["explicit"]]
    assert len(all_lines) == len(set(all_lines)), "duplicate freaky lines"
