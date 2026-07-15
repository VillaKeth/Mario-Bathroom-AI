# Mario Sings "My Way" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a spoken/typed "sing my way," Mario plays a pre-rendered AI voice-conversion cover of "My Way" (real singing in his voice) with a speech bubble, on the party speakers.

**Architecture:** Two independent halves. **Half A (offline):** `scripts/make_song_cover.py` turns a source recording into `characters/mario/songs/my_way.wav` via demucs (vocal isolation) → `rvc_python` (Martinet timbre) → `-3dB` normalize. **Half B (runtime):** a character-agnostic `server/performed_songs.py` registry loads per-character song assets; a trigger in `command_handlers.py` returns a `__PERFORMED_SONG__:<id>` sentinel (mirroring the existing `__SHOT_EVENT_TRIGGER__` pattern); `main.py` intercepts it and ships the pre-rendered WAV through the existing `send_response()` path — no TTS/model inference on the party hot path.

**Tech Stack:** Python 3, FastAPI WebSocket server, `rvc_python`, demucs, pytest.

## Global Constraints

- **Logging:** use `print()` in `command_handlers.py` (it has no `logger` import); `main.py`/`performed_songs.py` use `logger`.
- **WebSocket message type MUST be `"mario_response"`** (never `"response"`).
- **No ellipsis (`...`/`…`)** in any hardcoded string that reaches TTS/display.
- **Content pools default EMPTY** and populate only from the active character's own assets — never hardcode Mario song data into the module (mirrors `game_handlers.py`).
- **set_character convention:** any server module with user-visible text exposes `set_character(name, display_name)` + `_CHARACTER_NAME`/`_CHARACTER_DISPLAY_NAME` fallbacks.
- **Git:** stage specific files only (`git add <file>` — never `-A`; Qdrant `.lock` files must never be committed). Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- **Copyright:** the rendered `*.wav` stays local and is git-ignored; never commit song audio.
- **Character songs dir:** `os.path.join(_character.character_dir, "songs")` (mirrors the `sfx` dir wiring at `main.py:821`).

---

### Task 1: `performed_songs.py` registry module

Pure, standalone module (only `os`, `json`, `re`, `logging`) — the party-critical logic. Fully unit-tested.

**Files:**
- Create: `server/performed_songs.py`
- Test: `tests/test_performed_songs.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `set_character(name: str, display_name: str) -> None`
  - `load_songs(songs_dir: str | None) -> int` — clears the pool, loads every `*.json` in `songs_dir` whose referenced `wav` file exists; returns count loaded.
  - `match(text: str) -> str | None` — returns a song `id` if a trigger phrase matches (guarded: only for messages of ≤ 8 words); else `None`.
  - `get(song_id: str) -> dict | None` — returns `{"id", "title", "lyric_pages": list[str], "bubble": str, "wav_bytes": bytes}` or `None` if unknown/unreadable.
  - `clear() -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_performed_songs.py
import json, os, wave, struct, importlib

def _tiny_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(struct.pack("<800h", *([0] * 800)))  # 0.1s silence

def _write_song(d, sid="my_way", triggers=None, wav=True):
    triggers = triggers if triggers is not None else ["sing my way", "my way"]
    if wav:
        _tiny_wav(os.path.join(d, f"{sid}.wav"))
    with open(os.path.join(d, f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump({"id": sid, "title": "My Way", "triggers": triggers,
                   "wav": f"{sid}.wav",
                   "lyric_pages": ["And now, the end is near"]}, f)

def _fresh():
    import performed_songs
    importlib.reload(performed_songs)
    return performed_songs

def test_load_and_match(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    assert ps.load_songs(str(tmp_path)) == 1
    assert ps.match("hey mario sing my way please") == "my_way"
    assert ps.match("my way") == "my_way"

def test_no_match_for_unrelated_or_too_long(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    assert ps.match("what is your favorite game") is None
    # >8 words never matches even if it contains a trigger
    assert ps.match("could you possibly find it in your heart to sing my way for us") is None

def test_get_returns_bytes_and_bubble(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    ps.load_songs(str(tmp_path))
    ps.set_character("mario", "Mario")
    song = ps.get("my_way")
    assert song["title"] == "My Way"
    assert isinstance(song["wav_bytes"], bytes) and len(song["wav_bytes"]) > 44
    assert "Mario" in song["bubble"] and "My Way" in song["bubble"]

def test_missing_wav_is_skipped(tmp_path):
    ps = _fresh()
    _write_song(tmp_path, wav=False)
    assert ps.load_songs(str(tmp_path)) == 0
    assert ps.match("my way") is None

def test_empty_or_none_dir_is_empty_pool(tmp_path):
    ps = _fresh()
    assert ps.load_songs(None) == 0
    assert ps.load_songs(str(tmp_path)) == 0   # empty dir
    assert ps.match("my way") is None

def test_non_mario_bubble_uses_display_name(tmp_path):
    ps = _fresh()
    _write_song(tmp_path)
    ps.load_songs(str(tmp_path))
    ps.set_character("rudi", "Rudi")
    assert "Rudi" in ps.get("my_way")["bubble"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'performed_songs'` (or import error).

> Note: tests import `performed_songs` bare; run pytest from repo root with `server/` on `sys.path`. If the suite's `conftest.py` doesn't already add `server/`, add `import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))` at the top of the test file.

- [ ] **Step 3: Write the module**

```python
# server/performed_songs.py
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


def load_songs(songs_dir: str | None) -> int:
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


def match(text: str) -> str | None:
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


def get(song_id: str) -> dict | None:
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add server/performed_songs.py tests/test_performed_songs.py
git commit -m "feat(songs): performed-songs registry (load/match/get, empty-default)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Wire registry load into startup + character switch

`performed_songs` must be populated for the active character at startup and re-populated when the character switches.

**Files:**
- Modify: `server/main.py` (import near the other server-module imports; call at `main.py:781` startup block and `main.py:3211` switch block)

**Interfaces:**
- Consumes: `performed_songs.set_character`, `performed_songs.load_songs` (Task 1); `_character.character_dir`, `_character.name`, `_character.display_name` (existing).
- Produces: a populated `_SONGS` pool for the active character.

- [ ] **Step 1: Add the import**

Near the top module imports of `main.py` (with the other `import <server_module>` lines, e.g. beside `import sound_events`), add:

```python
import performed_songs
```

- [ ] **Step 2: Wire startup load**

In the startup block, immediately after the existing SFX wiring at `main.py:821-822`:

```python
        _char_sfx = os.path.join(_character.character_dir, "sfx")
        sound_events.set_character_sfx_dir(_char_sfx if os.path.isdir(_char_sfx) else None)
```

add:

```python
        performed_songs.set_character(_character.name, _character.display_name)
        performed_songs.load_songs(os.path.join(_character.character_dir, "songs"))
```

- [ ] **Step 3: Wire character-switch reload**

In the `switch_character` block, after the existing `command_handlers.set_character(...)` call at `main.py:3211`, add:

```python
        performed_songs.set_character(_character.name, _character.display_name)
        performed_songs.load_songs(os.path.join(_character.character_dir, "songs"))
```

- [ ] **Step 4: Smoke-test the import + startup path**

Run: `venv\Scripts\python -c "import sys; sys.path.insert(0,'server'); import performed_songs; print('ok', performed_songs.load_songs(None))"`
Expected: prints `ok 0` (no crash; empty pool when dir absent).

- [ ] **Step 5: Commit**

```bash
git add server/main.py
git commit -m "feat(songs): load performed-songs pool at startup and on character switch

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Trigger — return the `__PERFORMED_SONG__` sentinel

Detect a song request in `command_handlers` and return the sentinel string, mirroring the existing `__SHOT_EVENT_TRIGGER__:` pattern (`command_handlers.py:1526`).

**Files:**
- Modify: `server/command_handlers.py` (import at top; detection just before the Karaoke block at `command_handlers.py:1255`)
- Test: `tests/test_performed_songs_trigger.py`

**Interfaces:**
- Consumes: `performed_songs.match` (Task 1).
- Produces: `_handle_special_commands_impl(...)` returns `f"__PERFORMED_SONG__:{song_id}"` when a song matches; main.py (Task 4) consumes this prefix.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_performed_songs_trigger.py
import sys, os, json, wave, struct, importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

def _tiny_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(struct.pack("<800h", *([0] * 800)))

def test_trigger_returns_sentinel(tmp_path):
    import performed_songs
    importlib.reload(performed_songs)
    _tiny_wav(os.path.join(tmp_path, "my_way.wav"))
    with open(os.path.join(tmp_path, "my_way.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "my_way", "title": "My Way",
                   "triggers": ["sing my way", "my way"], "wav": "my_way.wav"}, f)
    performed_songs.load_songs(str(tmp_path))

    import command_handlers
    importlib.reload(command_handlers)
    # command_handlers imported performed_songs itself; point its reference at ours
    command_handlers.performed_songs = performed_songs

    state = command_handlers.new_state() if hasattr(command_handlers, "new_state") else {
        "_last_command_time": 0, "_active_game": None, "_game_state": {},
        "speaker_id": None, "speaker_name": None, "_detected_mood": None,
    }
    out = command_handlers._handle_special_commands_impl(
        "sing my way", state, {"command_cooldown": 0}, None, None, None, None)
    assert out == "__PERFORMED_SONG__:my_way"
```

> If `_handle_special_commands_impl` reaches code paths that need a fuller `state`/`game_config` before the song check, copy the minimal keys the karaoke-adjacent code reads (`_word_count` is derived from the transcript; `_active_game` must be falsy). Keep the song check EARLY (Step 3 places it right before Karaoke) so little state is required.

- [ ] **Step 2: Run test, verify it fails**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs_trigger.py -v`
Expected: FAIL — `AttributeError: module 'command_handlers' has no attribute 'performed_songs'` or `AssertionError` (returns None).

- [ ] **Step 3: Add the import + detection**

At the top of `command_handlers.py` (with the other `import <module>` lines, e.g. beside `import game_handlers`):

```python
import performed_songs
```

Then, immediately BEFORE the Karaoke block at `command_handlers.py:1255` (`# Karaoke mode`), insert:

```python
    # Performed song (real pre-rendered audio cover, e.g. "sing my way").
    # Checked before karaoke so a specific song wins over the generic game.
    # Returns a sentinel that main.py detects to ship the WAV directly (no TTS).
    _song_id = performed_songs.match(lower)
    if _song_id:
        print(f"[SONGS] performed-song trigger matched: {_song_id}")
        return f"__PERFORMED_SONG__:{_song_id}"

```

- [ ] **Step 4: Run test, verify it passes**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs_trigger.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/command_handlers.py tests/test_performed_songs_trigger.py
git commit -m "feat(songs): trigger performed-song sentinel before karaoke

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Delivery hook — ship the WAV, guard idle during playback

Intercept the sentinel in `_generate_and_send_response` and deliver the pre-rendered WAV via `send_response()`; suppress idle chatter for the song's duration using a timestamp guard.

**Files:**
- Modify: `server/main.py` — hook after `main.py:4812`; new helper `_deliver_performed_song`; idle guard in `_idle_send_if_safe` (`main.py:4148`)
- Test: `tests/test_deliver_performed_song.py`

**Interfaces:**
- Consumes: `performed_songs.get` (Task 1); `send_response(ws, text, audio=, emotion=)` (`main.py:7328`); `_wav_secs(wav_bytes) -> float` (existing, used at `main.py:1395`); module global `state_current`.
- Produces: `state_current["_performing_song_until"]` (float epoch seconds; `0`/absent = not performing) — read by the idle guard and cleared by Task 5.

- [ ] **Step 1: Write the failing test** (helper logic is async; test the guard-timestamp + send via a fake ws)

```python
# tests/test_deliver_performed_song.py
import sys, os, asyncio, importlib, wave, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

def _tiny_wav_bytes():
    import io
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(struct.pack("<8000h", *([0] * 8000)))  # 1.0s
    return b.getvalue()

class FakeWS:
    def __init__(self): self.jsons = []; self.blobs = []
    async def send_json(self, m): self.jsons.append(m)
    async def send_bytes(self, b): self.blobs.append(b)

def test_deliver_sets_guard_and_sends(monkeypatch):
    import performed_songs, main
    importlib.reload(performed_songs)
    wavb = _tiny_wav_bytes()
    monkeypatch.setattr(main.performed_songs, "get", lambda sid: {
        "id": sid, "title": "My Way", "lyric_pages": [],
        "bubble": "🎤 Mario sings My Way ♪", "wav_bytes": wavb})
    main.state_current["_performing_song_until"] = 0.0
    ws = FakeWS()
    asyncio.run(main._deliver_performed_song(ws, "my_way"))
    # bubble json + audio bytes both sent
    assert any(j.get("type") == "mario_response" for j in ws.jsons)
    assert ws.blobs and ws.blobs[0] == wavb
    # guard set into the future (song is ~1s)
    assert main.state_current["_performing_song_until"] > main.time.time()
```

> `main` imports heavy deps; if importing `main` in the test env is impractical, mark this file `pytest.importorskip("main")` at top and rely on the live audio verification (Step 6) as the real gate. The registry (Task 1) already carries full unit coverage.

- [ ] **Step 2: Run test, verify it fails**

Run: `venv\Scripts\python -m pytest tests/test_deliver_performed_song.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_deliver_performed_song'`.

- [ ] **Step 3: Add the delivery hook**

In `_generate_and_send_response`, immediately after `main.py:4812` (`response_text = await _handle_special_commands(text)`) and before the `_timing["commands_ms"]` line, insert:

```python
        if response_text and response_text.startswith("__PERFORMED_SONG__:"):
            await _deliver_performed_song(ws, response_text.split(":", 1)[1])
            return
```

- [ ] **Step 4: Add the helper** (place near `send_response`, e.g. after `main.py:7325`)

```python
async def _deliver_performed_song(ws: WebSocket, song_id: str):
    """Ship a pre-rendered song cover (real audio) to the client, bypassing TTS.
    Sets a timestamp guard so the idle loop stays quiet while it plays."""
    song = performed_songs.get(song_id)
    if not song:
        logger.warning(f"[SONGS] deliver: unknown/unreadable song '{song_id}'")
        return
    wav = song["wav_bytes"]
    try:
        dur = _wav_secs(wav)
    except Exception:
        dur = 30.0
    # Guard covers playback + a small tail so idle can't jump in at the end.
    state_current["_performing_song_until"] = time.time() + dur + 3.0
    logger.info(f"[SONGS] performing '{song_id}' ({dur:.0f}s): {song['title']}")
    await send_response(ws, song["bubble"], audio=wav, emotion="excited")
```

- [ ] **Step 5: Add the idle guard**

At the top of `_idle_send_if_safe` (`main.py:4148`), before any send logic, add:

```python
    if time.time() < state_current.get("_performing_song_until", 0.0):
        logger.debug("[IDLE] suppressed — performing a song")
        return
```

- [ ] **Step 6: Run unit test + LIVE audio verification**

Run: `venv\Scripts\python -m pytest tests/test_deliver_performed_song.py -v` → PASS (or skipped per note).

Then per `.claude/rules/testing.md` (MANDATORY — audio, not just logs), with server + client running and a placeholder `my_way.wav` present (Task 7 creates the real one):
- Send "sing my way" (typed or admin `simulate_text`).
- Confirm client log: `[audio_playback] _play_wav: playing <bytes>` AND `[audio_playback] _play_wav: done`.
- Confirm the speech bubble reads "🎤 Mario sings My Way ♪".
- While it plays, confirm NO idle mumble is emitted (guard works).

- [ ] **Step 7: Commit**

```bash
git add server/main.py tests/test_deliver_performed_song.py
git commit -m "feat(songs): deliver pre-rendered song WAV, guard idle during playback

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Stop interruption

Let a guest cut the song short with "stop."

**Files:**
- Modify: `server/command_handlers.py` (early check in `_handle_special_commands_impl`), `server/main.py` (sentinel handler beside the song hook)
- Test: extend `tests/test_performed_songs_trigger.py`

**Interfaces:**
- Consumes: `state_current["_performing_song_until"]` (Task 4).
- Produces: sentinel `"__STOP_SONG__"`; main.py sends `{"type": "clear_audio"}` and zeroes the guard.

- [ ] **Step 1: Write the failing test** (append to `tests/test_performed_songs_trigger.py`)

```python
def test_stop_during_song_returns_stop_sentinel(tmp_path):
    import importlib, command_handlers
    importlib.reload(command_handlers)
    state = {
        "_last_command_time": 0, "_active_game": None, "_game_state": {},
        "speaker_id": None, "speaker_name": None, "_detected_mood": None,
        "_performing_song_until": 9e18,  # currently performing
    }
    out = command_handlers._handle_special_commands_impl(
        "stop", state, {"command_cooldown": 0}, None, None, None, None)
    assert out == "__STOP_SONG__"
```

- [ ] **Step 2: Run, verify fail**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs_trigger.py::test_stop_during_song_returns_stop_sentinel -v`
Expected: FAIL (returns None).

- [ ] **Step 3: Add the stop check** — at the very start of `_handle_special_commands_impl`, right after `lower = transcript.lower()` (`command_handlers.py:474`) and before the cooldown early-return:

```python
    # Stop an in-progress performed song (checked first so it beats the cooldown).
    if state.get("_performing_song_until", 0.0) > time.time():
        if any(w in lower for w in ["stop", "enough", "quiet", "shut up", "cut it"]):
            print("[SONGS] stop requested during performance")
            return "__STOP_SONG__"
```

- [ ] **Step 4: Add the main.py handler** — beside the song hook after `main.py:4812`, add above the `__PERFORMED_SONG__` block:

```python
        if response_text == "__STOP_SONG__":
            state_current["_performing_song_until"] = 0.0
            try:
                await ws.send_json({"type": "clear_audio"})
            except Exception as e:
                logger.debug(f"[SONGS] clear_audio send failed: {e}")
            return
```

- [ ] **Step 5: Run test, verify pass**

Run: `venv\Scripts\python -m pytest tests/test_performed_songs_trigger.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add server/command_handlers.py server/main.py tests/test_performed_songs_trigger.py
git commit -m "feat(songs): 'stop' interrupts an in-progress performed song

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Production script `scripts/make_song_cover.py`

Offline CLI: source recording → demucs (isolate vocals) → `rvc_python` (Mario timbre) → `-3dB` normalize → `characters/<char>/songs/<id>.wav`. Pure helpers are unit-tested; the full pipeline is a manual run (needs GPU + a source file, not CI).

**Files:**
- Create: `scripts/make_song_cover.py`
- Test: `tests/test_make_song_cover.py`

**Interfaces:**
- Consumes: `demucs` (CLI `python -m demucs`), `rvc_python.infer.RVCInference`, `server/tts.py` `_normalize_audio` + `RVC_MODEL_PATH` / `RVC_INDEX_PATH`.
- Produces: pure helpers `demucs_stem_path(outdir, input_path)` and `rvc_params(f0_up_key, index_rate, protect)`; `main(argv)` wiring.

- [ ] **Step 1: Write the failing tests** (pure helpers only)

```python
# tests/test_make_song_cover.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import make_song_cover as m

def test_demucs_stem_path():
    p = m.demucs_stem_path("/out", "/music/My Way.mp3")
    # demucs writes <out>/htdemucs/<track-name>/vocals.wav
    assert p.replace("\\", "/") == "/out/htdemucs/My Way/vocals.wav"

def test_rvc_params_preserve_melody_by_default():
    params = m.rvc_params(0, 0.6, 0.25)
    assert params["f0up_key"] == 0        # melody preserved (NOT +12 like speech)
    assert params["index_rate"] == 0.6
    assert params["protect"] == 0.25
    assert params["f0method"] == "rmvpe"
```

- [ ] **Step 2: Run, verify fail**

Run: `venv\Scripts\python -m pytest tests/test_make_song_cover.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'make_song_cover'`.

- [ ] **Step 3: Write the script**

```python
# scripts/make_song_cover.py
"""Offline: turn a source recording into a character-voice singing cover.

Pipeline:  source -> demucs (isolate vocals) -> rvc_python (character timbre)
           -> peak-normalize -3dB -> characters/<char>/songs/<id>.wav

Melody is preserved (f0_up_key defaults to 0); the speech path's +12 semitone
shift would wreck a sung melody. Re-run with different --f0-up-key / --index-rate
/ --protect until it sings right. Rendered wav is LOCAL ONLY (copyright).

Example:
  gpt_sovits_env\\Scripts\\python scripts/make_song_cover.py \\
      --in "My Way.mp3" --char mario --id my_way --title "My Way"
"""
import os
import sys
import argparse
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "server"))


def demucs_stem_path(outdir: str, input_path: str) -> str:
    """Where demucs (default htdemucs model) writes the isolated vocal stem."""
    track = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(outdir, "htdemucs", track, "vocals.wav")


def rvc_params(f0_up_key: int, index_rate: float, protect: float) -> dict:
    """RVC params tuned for SINGING (melody-preserving), unlike the speech path."""
    return {
        "f0method": "rmvpe",
        "f0up_key": int(f0_up_key),
        "index_rate": float(index_rate),
        "protect": float(protect),
    }


def isolate_vocals(input_path: str, outdir: str, python_exe: str = sys.executable) -> str:
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(
        [python_exe, "-m", "demucs", "--two-stems=vocals", "-o", outdir, input_path],
        check=True,
    )
    stem = demucs_stem_path(outdir, input_path)
    if not os.path.isfile(stem):
        raise FileNotFoundError(f"demucs did not produce {stem}")
    return stem


def convert_to_character(vocals_path: str, out_wav: str, params: dict) -> str:
    from rvc_python.infer import RVCInference
    import tts
    rvc = RVCInference()
    rvc.load_model(tts.RVC_MODEL_PATH)
    rvc.set_params(**params)
    tmp = out_wav + ".raw.wav"
    rvc.infer_file(vocals_path, tmp)
    with open(tmp, "rb") as f:
        raw = f.read()
    normalized = tts._normalize_audio(raw)
    with open(out_wav, "wb") as f:
        f.write(normalized)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out_wav


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="source audio (mp3/wav)")
    ap.add_argument("--char", default="mario")
    ap.add_argument("--id", dest="song_id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--f0-up-key", type=int, default=0)
    ap.add_argument("--index-rate", type=float, default=0.6)
    ap.add_argument("--protect", type=float, default=0.25)
    ap.add_argument("--workdir", default=os.path.join(_ROOT, "scripts", "_song_work"))
    args = ap.parse_args(argv)

    songs_dir = os.path.join(_ROOT, "characters", args.char, "songs")
    os.makedirs(songs_dir, exist_ok=True)
    out_wav = os.path.join(songs_dir, f"{args.song_id}.wav")

    print(f"[1/3] isolating vocals from {args.inp}")
    vocals = isolate_vocals(args.inp, args.workdir)
    print(f"[2/3] RVC -> {args.char} timbre  params={rvc_params(args.f0_up_key, args.index_rate, args.protect)}")
    convert_to_character(vocals, out_wav, rvc_params(args.f0_up_key, args.index_rate, args.protect))
    print(f"[3/3] wrote {out_wav}")
    print(f"Now create characters/{args.char}/songs/{args.song_id}.json (see the design spec).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `venv\Scripts\python -m pytest tests/test_make_song_cover.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/make_song_cover.py tests/test_make_song_cover.py
git commit -m "feat(songs): offline make_song_cover.py (demucs -> RVC -> normalize)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Asset, gitignore, generate the real WAV, live verify

Create the song metadata + placeholder, ensure audio is never committed, produce the real cover, and verify end-to-end with audio.

**Files:**
- Create: `characters/mario/songs/my_way.json`
- Modify: `.gitignore`
- Generate (local, not committed): `characters/mario/songs/my_way.wav`

**Interfaces:**
- Consumes: everything above.
- Produces: a working, playable performance.

- [ ] **Step 1: Write the song metadata**

`characters/mario/songs/my_way.json`:

```json
{
  "id": "my_way",
  "title": "My Way",
  "triggers": ["sing my way", "my way", "do it your way"],
  "wav": "my_way.wav",
  "lyric_pages": [
    "And now, the end is near ♪",
    "And so I face the final curtain ♪"
  ],
  "bubble": "🎤 Mario sings My Way ♪",
  "credits": "AI cover — private party use only, not for distribution"
}
```

- [ ] **Step 2: Ignore song audio (never commit copyrighted WAVs)**

Append to `.gitignore`:

```
# Performed-song audio (copyright — kept local only)
characters/*/songs/*.wav
```

Verify: `git check-ignore characters/mario/songs/my_way.wav` → prints the path (ignored).

- [ ] **Step 3: Create a placeholder WAV so runtime loads before the real render exists**

Run:
```bash
venv\Scripts\python -c "import wave,struct,os; os.makedirs('characters/mario/songs',exist_ok=True); w=wave.open('characters/mario/songs/my_way.wav','wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(struct.pack('<22050h',*([0]*22050))); w.close(); print('placeholder written')"
```

- [ ] **Step 4: Generate the real cover** (manual; needs a source recording + the RVC env)

```bash
gpt_sovits_env\Scripts\python scripts/make_song_cover.py --in "<path to My Way recording>.mp3" --char mario --id my_way --title "My Way"
```
Re-run with e.g. `--f0-up-key 3 --index-rate 0.5` and A/B until it sounds like Mario without wrecking the key (see spec §5). This overwrites the placeholder `my_way.wav`.

- [ ] **Step 5: Commit metadata + gitignore (NOT the wav)**

```bash
git add characters/mario/songs/my_way.json .gitignore
git commit -m "feat(songs): add Mario 'My Way' song metadata; ignore local song audio

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Confirm `git status` shows NO `my_way.wav` (it must be ignored).

- [ ] **Step 6: Full live audio verification** (`.claude/rules/testing.md`)

With server + client running and the REAL `my_way.wav` in place:
- "sing my way" → client logs `_play_wav: playing` AND `_play_wav: done`; bubble "🎤 Mario sings My Way ♪"; audio is Mario singing the melody (not speech).
- No idle mumble during playback.
- "stop" mid-song → audio cuts (`clear_audio`) and idle resumes after.
- Full suite still green: `venv\Scripts\python -m pytest tests/ -q`.

---

## Self-Review

**Spec coverage:**
- §3 two halves → Tasks 6 (A) + 1–5 (B). ✅
- §4 registry approach → Task 1. ✅
- §5 production pipeline (demucs→RVC→normalize, f0_up_key=0) → Task 6. ✅
- §6 asset format → Tasks 1 (loader) + 7 (my_way.json). ✅
- §7 runtime module (set_character, empty default, match/get) → Task 1. ✅
- §8 trigger + bypass-TTS delivery + guard + interrupt → Tasks 3, 4, 5. ✅
- §9 error handling (missing wav skipped, non-Mario empty, guard cleared) → Tasks 1, 4, 5. ✅
- §10 testing (unit + live audio) → every task's tests + Tasks 4/7 live steps. ✅
- §11 copyright (local, not committed) → Task 7 gitignore. ✅

**Placeholder scan:** every code step contains full code; no TBD/TODO. The only manual step (Task 7 Step 4) is inherently manual (needs a source recording + GPU) and is explicitly marked. ✅

**Type consistency:** `load_songs`/`match`/`get`/`set_character`/`clear` names are identical across Tasks 1–5. Sentinels `__PERFORMED_SONG__:<id>` and `__STOP_SONG__` match between producer (command_handlers) and consumer (main.py). Guard key `_performing_song_until` identical in Tasks 4 and 5. `rvc_params`/`demucs_stem_path` match between Task 6 code and its tests. ✅

**Ordering note:** Task 4's delivery hook and Task 5's stop hook both sit just after `main.py:4812`; Task 5 Step 4 places the stop block ABOVE the song block — apply them in order (Task 4 then Task 5).
