"""F5: multi-sample voice enrollment — average several clips into one robust print.

_average_embeddings is pure (no model). register_speaker_multi is tested with
get_embedding monkeypatched so it needs no VoiceEncoder.
"""
import sys
import os
import sqlite3
import tempfile
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import speaker_id  # noqa: E402


# ----------------- _average_embeddings (pure) -----------------
def test_average_of_single_vector_is_unit_normalized():
    v = np.array([3.0, 4.0] + [0.0] * 254)  # norm 5
    out = speaker_id._average_embeddings([v])
    assert np.isclose(np.linalg.norm(out), 1.0)
    assert np.allclose(out[:2], [0.6, 0.8])


def test_average_of_identical_unit_vectors_is_same():
    v = np.zeros(256); v[0] = 1.0
    out = speaker_id._average_embeddings([v, v, v])
    assert np.allclose(out, v)


def test_average_result_is_unit_norm():
    a = np.zeros(256); a[0] = 1.0
    b = np.zeros(256); b[1] = 1.0
    out = speaker_id._average_embeddings([a, b])
    assert np.isclose(np.linalg.norm(out), 1.0)
    assert out[0] > 0 and out[1] > 0


def test_average_ignores_none_entries():
    v = np.zeros(256); v[5] = 2.0
    out = speaker_id._average_embeddings([None, v, None])
    assert np.isclose(np.linalg.norm(out), 1.0)


def test_average_of_empty_is_none():
    assert speaker_id._average_embeddings([]) is None
    assert speaker_id._average_embeddings([None, None]) is None


# ----------------- register_speaker_multi (monkeypatched encoder) -----------------
def test_register_speaker_multi_averages_and_stores(tmp_path, monkeypatch):
    monkeypatch.setattr(speaker_id, "DB_PATH", str(tmp_path / "voices.db"))
    monkeypatch.setattr(speaker_id, "_encoder", object())  # bypass the unavailable guard

    a = np.zeros(256); a[0] = 1.0
    b = np.zeros(256); b[1] = 1.0
    chunks = [b"chunkA", b"chunkB"]
    seq = {b"chunkA": a, b"chunkB": b}
    monkeypatch.setattr(speaker_id, "get_embedding", lambda data, sr=16000: seq[data])

    # init the speakers table
    with sqlite3.connect(speaker_id.DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS speakers (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     " name TEXT NOT NULL, embedding BLOB NOT NULL, created_at TIMESTAMP)")

    sid = speaker_id.register_speaker_multi("Robin", chunks)
    assert sid is not None

    with sqlite3.connect(speaker_id.DB_PATH) as conn:
        row = conn.execute("SELECT name, embedding FROM speakers WHERE id=?", (sid,)).fetchone()
    assert row[0] == "Robin"
    stored = np.frombuffer(row[1], dtype=np.float32).astype(np.float64)
    expected = speaker_id._average_embeddings([a, b])
    assert np.allclose(stored, expected, atol=1e-6)


def test_register_speaker_multi_skips_unusable_and_raises_when_all_bad(tmp_path, monkeypatch):
    monkeypatch.setattr(speaker_id, "DB_PATH", str(tmp_path / "voices.db"))
    monkeypatch.setattr(speaker_id, "_encoder", object())
    monkeypatch.setattr(speaker_id, "get_embedding", lambda data, sr=16000: None)  # all too quiet
    with sqlite3.connect(speaker_id.DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS speakers (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     " name TEXT NOT NULL, embedding BLOB NOT NULL, created_at TIMESTAMP)")
    try:
        speaker_id.register_speaker_multi("Nobody", [b"x", b"y"])
        assert False, "expected ValueError"
    except ValueError:
        pass
