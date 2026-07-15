"""Registry of pre-rendered "performed songs" (real audio files) a character
can play on command. Character-agnostic: pools default empty and are populated
only from the active character's own characters/<char>/songs/ assets, so no
character ever inherits another's songs. See
docs/superpowers/specs/2026-07-15-mario-sings-my-way-design.md
"""
import os
import json
import logging

logger = logging.getLogger("performed_songs")

_CHARACTER_NAME = "Mario"
_CHARACTER_DISPLAY_NAME = "Mario"

# id -> {"id","title","triggers":[...],"wav_path","lyric_pages":[...],"bubble"?}
_SONGS: dict = {}

_MAX_TRIGGER_WORDS = 8  # guard: ignore long conversational messages


def set_character(name: str, display_name: str) -> None:
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    _CHARACTER_NAME = name or "Mario"
    _CHARACTER_DISPLAY_NAME = display_name or name or "Mario"


def clear() -> None:
    _SONGS.clear()


def load_songs(songs_dir) -> int:
    """Clear the pool, then load every valid *.json song in songs_dir.
    A song is valid only if its referenced wav file exists on disk."""
    _SONGS.clear()
    if not songs_dir or not os.path.isdir(songs_dir):
        logger.info(f"[SONGS] no songs dir ({songs_dir}) — pool empty")
        return 0
    for fn in sorted(os.listdir(songs_dir)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(songs_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[SONGS] bad json {fn}: {e}")
            continue
        sid = data.get("id") or os.path.splitext(fn)[0]
        wav = data.get("wav") or f"{sid}.wav"
        wav_path = os.path.join(songs_dir, wav)
        if not os.path.isfile(wav_path):
            logger.warning(f"[SONGS] {sid}: wav missing ({wav_path}) — skipped")
            continue
        triggers = [t.lower() for t in data.get("triggers", []) if t]
        _SONGS[sid] = {
            "id": sid,
            "title": data.get("title", sid),
            "triggers": triggers,
            "wav_path": wav_path,
            "lyric_pages": list(data.get("lyric_pages", [])),
            "bubble": data.get("bubble"),
        }
    logger.info(f"[SONGS] loaded {len(_SONGS)} song(s) from {songs_dir}")
    return len(_SONGS)


def match(text):
    """Return a song id if a trigger phrase is present (short messages only)."""
    if not text or not _SONGS:
        return None
    lower = text.lower()
    if len(lower.split()) > _MAX_TRIGGER_WORDS:
        return None
    # Prefer the longest trigger phrase across all songs (most specific wins).
    best = None  # (trigger_len, song_id)
    for sid, song in _SONGS.items():
        for trig in song["triggers"]:
            if trig and trig in lower:
                if best is None or len(trig) > best[0]:
                    best = (len(trig), sid)
    return best[1] if best else None


def get(song_id):
    song = _SONGS.get(song_id)
    if not song:
        return None
    try:
        with open(song["wav_path"], "rb") as f:
            wav_bytes = f.read()
    except Exception as e:
        logger.error(f"[SONGS] read failed for {song_id}: {e}")
        return None
    bubble = song["bubble"] or f"🎤 {_CHARACTER_DISPLAY_NAME} sings {song['title']} ♪"
    return {
        "id": song_id,
        "title": song["title"],
        "lyric_pages": song["lyric_pages"],
        "bubble": bubble,
        "wav_bytes": wav_bytes,
    }
