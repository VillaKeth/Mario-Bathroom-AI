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
