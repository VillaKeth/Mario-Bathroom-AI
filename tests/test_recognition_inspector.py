"""Tests for the Recognition Inspector (server/recognition_events.py + main.py routes)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import recognition_events as re_mod


def setup_function(_):
    re_mod._events.clear()
    re_mod._seq = 0


def test_push_appends_and_assigns_increasing_seq():
    a = re_mod.push("face", "Alice", 0.82, False, "live")
    b = re_mod.push("voice", "Bob", 0.71, False, "upload")
    assert a["seq"] == 1 and b["seq"] == 2
    assert a["kind"] == "face" and a["name"] == "Alice" and a["source"] == "live"
    assert "ts" in a


def test_recent_filters_by_since():
    re_mod.push("face", "A", 1.0, True, "live")
    re_mod.push("face", "B", 1.0, True, "live")
    assert [e["name"] for e in re_mod.recent(since=0)] == ["A", "B"]
    assert [e["name"] for e in re_mod.recent(since=1)] == ["B"]
    assert re_mod.recent(since=2) == []


def test_person_id_for_name_is_stable_and_distinct():
    assert re_mod.person_id_for_name("Alice") == re_mod.person_id_for_name("alice")
    assert re_mod.person_id_for_name("Alice") != re_mod.person_id_for_name("Bob")
    assert isinstance(re_mod.person_id_for_name("Alice"), int)


import ast

_MAIN = os.path.join(os.path.dirname(__file__), "..", "server", "main.py")


def _main_src():
    with open(_MAIN, encoding="utf-8") as f:
        return f.read()


def test_main_imports_recognition_events():
    assert "import recognition_events" in _main_src()


def test_roster_and_events_routes_declared():
    src = _main_src()
    assert '"/recognition"' in src or "'/recognition'" in src
    assert "/admin/recognition/roster" in src
    assert "/admin/recognition/events" in src


def test_recognition_html_stub_exists():
    p = os.path.join(os.path.dirname(__file__), "..", "server", "static", "recognition.html")
    assert os.path.exists(p), "server/static/recognition.html must exist"


import numpy as np
import recognition_events as _re2


def test_face_store_then_find_roundtrip(tmp_path):
    # Reuse the real face_memory module against a temp DB; synthetic 128-dim vector.
    import face_memory
    fm = face_memory.FaceMemory(str(tmp_path / "faces.db"))
    enc = np.zeros(128, dtype=np.float64); enc[0] = 1.0
    pid = _re2.person_id_for_name("TestAlice")
    fm.store_face(pid, "TestAlice", enc)
    m = fm.find_match(enc)
    assert m is not None and m["name"] == "TestAlice" and m["confidence"] > 0.95
    far = np.zeros(128, dtype=np.float64); far[1] = 5.0
    assert fm.find_match(far) is None  # beyond 0.6 tolerance


def test_face_voice_routes_declared():
    src = _main_src()
    assert "/admin/recognition/face" in src
    assert "/admin/recognition/voice" in src


def test_recognition_html_has_three_panels_and_calls():
    p = os.path.join(os.path.dirname(__file__), "..", "server", "static", "recognition.html")
    html = open(p, encoding="utf-8").read()
    for needle in ("/admin/recognition/roster", "/admin/recognition/face",
                   "/admin/recognition/voice", "/admin/recognition/events",
                   "image_b64", "wav_b64"):
        assert needle in html, f"recognition.html must reference {needle}"


def test_live_paths_push_recognition_events():
    src = _main_src()
    tree = ast.parse(src)
    def fn(name):
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
                return n
    def calls_push(node):
        for c in ast.walk(node):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
               and c.func.attr == "push" and isinstance(c.func.value, ast.Name) \
               and c.func.value.id == "recognition_events":
                return True
        return False
    assert calls_push(fn("handle_event")), "person_detected handler must push a face event"
    # voice path lives in the audio handler function:
    audio_fn = fn("_process_audio") or fn("handle_audio")
    assert audio_fn and calls_push(audio_fn), "audio path must push a voice event"
