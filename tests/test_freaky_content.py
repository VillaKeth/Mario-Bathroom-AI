import os, re, yaml
from server.joke_engine import load_freaky_jokes

RUDI = os.path.join("characters", "rudi")

# Defense-in-depth blocklist: the freaky pool is intentionally crude, but the
# hard line (no hate slurs, nothing sexual about minors, no non-consent) is
# absolute. This catches an over-line item slipping into freaky.yaml on a
# future edit even though the current pool is clean. Word-boundary, tight and
# unambiguous so it does NOT trip legitimate raunch.
_HARDLINE = re.compile(
    r"\b("
    r"rape|raping|rapist|molest\w*|noncon\w*|non-con\w*|roofie\w*|drugged|"   # non-consent
    r"underage|jailbait|loli|shota|preteen|pre-teen|"                          # minors
    r"faggot|retard|tranny|chink|spic"                                         # hate slurs (subset)
    r")\b", re.IGNORECASE)
# Numeric-age sneak (e.g. "16yo", "15 year"): a 10-17 followed by an age unit.
_AGE = re.compile(r"\b1[0-7]\s?(yo|y/o|years?)\b", re.IGNORECASE)

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

def test_rudi_freaky_no_hardline_terms():
    fp = load_freaky_jokes(RUDI)
    hits = [ln for ln in fp["bravado"] + fp["explicit"]
            if _HARDLINE.search(ln) or _AGE.search(ln)]
    assert not hits, f"hard-line terms in freaky pool: {hits}"
