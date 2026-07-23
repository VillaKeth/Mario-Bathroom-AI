"""Tests for server/face_enrollment.py — the testable face-resolution logic
extracted from main.py's person_detected handler.

Covers the bugs from AUDIT_VOICE_FACE_RECOGNITION.md:
- F1: unknown face + known speaker must ENROLL (learn_guest), not crash.
- F2: unknown face + no speaker must be STASHED, then linkable by name later.
- F4: a matched face must surface its person_id (not a missing "id" key).
"""
import sys
import os
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import face_enrollment  # noqa: E402
import recognition_config  # noqa: E402
from face_memory import FaceMemory  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_recognition_config():
    """recognition_config caches tunables process-wide, so an override left behind by
    another test file could otherwise change the margin/quality outcomes asserted here."""
    recognition_config.reset_cache()
    yield
    recognition_config.reset_cache()


class FakeFaceMemory:
    """Duck-typed stand-in for FaceMemory; records enroll calls."""
    def __init__(self, match_result=None):
        self._match_result = match_result
        self.learned = []          # list of (name, encoding)

    def find_match(self, encoding, tolerance=None):
        return self._match_result

    def learn_guest(self, name, encoding, quality=0.0):
        self.learned.append((name, np.asarray(encoding)))
        return 1


def _face(enc):
    return {"encoding": list(enc), "confidence": 0.9}


def test_known_face_returns_name_person_id_and_confidence():
    """F4: a matched face surfaces person_id + confidence (not an absent 'id')."""
    fm = FakeFaceMemory(match_result={"name": "Alice", "person_id": 7, "visit_count": 3, "confidence": 0.82})
    res = face_enrollment.resolve_faces([_face(np.ones(128))], fm, speaker_name=None)
    assert res["detected"] == [{"name": "Alice", "person_id": 7, "visit_count": 3, "confidence": 0.82}]
    assert res["new_face_count"] == 0
    assert res["pending_encoding"] is None
    assert fm.learned == []  # known face must not re-enroll


def test_unknown_face_with_known_speaker_enrolls():
    """F1: unknown face + known speaker → learn_guest(speaker, enc)."""
    fm = FakeFaceMemory(match_result=None)
    enc = np.arange(128, dtype=np.float64)
    res = face_enrollment.resolve_faces([_face(enc)], fm, speaker_name="Bob")
    assert len(fm.learned) == 1
    name, learned_enc = fm.learned[0]
    assert name == "Bob"
    assert np.allclose(learned_enc, enc)
    assert "Bob" in [d["name"] for d in res["detected"]]
    assert res["new_face_count"] == 0
    assert res["pending_encoding"] is None


def test_unknown_face_no_speaker_is_stashed():
    """F2: unknown face + no speaker → stash for later naming, do not enroll."""
    fm = FakeFaceMemory(match_result=None)
    enc = np.arange(128, dtype=np.float64)
    res = face_enrollment.resolve_faces([_face(enc)], fm, speaker_name=None)
    assert fm.learned == []
    assert res["new_face_count"] == 1
    assert res["pending_encoding"] is not None
    assert np.allclose(res["pending_encoding"], enc)


def test_invalid_encoding_is_skipped():
    """Wrong-length encodings are ignored, valid ones in the same batch still process."""
    fm = FakeFaceMemory(match_result=None)
    faces = [{"encoding": [0.1, 0.2, 0.3], "confidence": 0.9},  # too short
             _face(np.zeros(128))]                              # valid, unknown, no speaker
    res = face_enrollment.resolve_faces(faces, fm, speaker_name=None)
    assert res["new_face_count"] == 1  # only the valid one counted


def test_nan_encoding_is_skipped():
    fm = FakeFaceMemory(match_result=None)
    bad = np.zeros(128); bad[0] = np.nan
    res = face_enrollment.resolve_faces([_face(bad)], fm, speaker_name="Bob")
    assert fm.learned == []
    assert res["new_face_count"] == 0


def test_missing_encoding_key_is_skipped():
    fm = FakeFaceMemory(match_result=None)
    res = face_enrollment.resolve_faces([{"confidence": 0.5}], fm, speaker_name="Bob")
    assert fm.learned == []
    assert res["detected"] == []


def test_link_pending_face_enrolls_by_name():
    """F2: once the guest gives a name, the stashed face is enrolled to it."""
    fm = FakeFaceMemory()
    enc = np.arange(128, dtype=np.float64)
    linked = face_enrollment.link_pending_face(fm, "Ann", enc)
    assert linked is True
    assert len(fm.learned) == 1
    assert fm.learned[0][0] == "Ann"


def test_link_pending_face_noops_when_nothing_pending():
    fm = FakeFaceMemory()
    assert face_enrollment.link_pending_face(fm, "Ann", None) is False
    assert fm.learned == []


def test_link_pending_face_noops_without_name():
    fm = FakeFaceMemory()
    assert face_enrollment.link_pending_face(fm, "", np.zeros(128)) is False
    assert fm.learned == []


def _enc(seed):
    """Deterministic distinct 128-dim encoding."""
    rng = np.random.default_rng(seed)
    return rng.random(128).tolist()


def test_single_unknown_face_with_speaker_enrolls_one():
    mem = FakeFaceMemory(match_result=None)
    out = face_enrollment.resolve_faces([{"encoding": _enc(1)}], mem, "Jacob")
    assert len(mem.learned) == 1
    assert mem.learned[0][0] == "Jacob"
    assert out["ambiguous"] is False


def test_multiple_unknown_faces_with_speaker_enroll_nothing():
    """Three strangers + a known speaker must NOT all become that speaker."""
    mem = FakeFaceMemory(match_result=None)
    faces = [{"encoding": _enc(1)}, {"encoding": _enc(2)}, {"encoding": _enc(3)}]
    out = face_enrollment.resolve_faces(faces, mem, "Jacob")
    assert mem.learned == []
    assert out["ambiguous"] is True
    assert out["new_face_count"] == 3


def test_multiple_unknown_faces_no_speaker_stash_nothing():
    mem = FakeFaceMemory(match_result=None)
    faces = [{"encoding": _enc(1)}, {"encoding": _enc(2)}]
    out = face_enrollment.resolve_faces(faces, mem, None)
    assert out["pending_encoding"] is None
    assert out["ambiguous"] is True


def test_single_unknown_face_no_speaker_stashes():
    mem = FakeFaceMemory(match_result=None)
    out = face_enrollment.resolve_faces([{"encoding": _enc(1)}], mem, None)
    assert out["pending_encoding"] is not None
    assert out["ambiguous"] is False


# ---------------------------------------------------------------------------
# Final-review CRITICAL 1 — an AMBIGUOUS match (the W4 margin firing) must never
# be mistaken for "nobody is close".
#
# These run against a REAL FaceMemory on a tmp_path DB, because the defect only
# appears through find_match's own margin logic: two enrolled people, a probe
# between them, and a `None` return that resolve_faces cannot distinguish from
# "this is a stranger". Enrolling there writes one guest's face into the OTHER
# guest's gallery, after which every later frame matches the wrong name at
# distance ~0 and clears the margin easily — a permanent, CONFIDENT wrong name.
# ---------------------------------------------------------------------------


def _two_person_gallery(tmp_path):
    """Alice at 0.0 and Bob at 0.40 on axis 0; a probe at 0.20 is equidistant."""
    mem = FaceMemory(str(tmp_path / "faces.db"))
    alice = np.zeros(128)
    bob = np.zeros(128); bob[0] = 0.40
    alice_pid = mem.learn_guest("Alice", alice)
    bob_pid = mem.learn_guest("Bob", bob)
    probe = np.zeros(128); probe[0] = 0.20
    return mem, alice_pid, bob_pid, probe


def test_ambiguous_face_is_not_enrolled_under_the_speakers_name(tmp_path):
    """An ambiguous probe + a known speaker must NOT poison that speaker's gallery."""
    mem, _alice_pid, bob_pid, probe = _two_person_gallery(tmp_path)
    assert mem.find_match(probe) is None          # margin fires: ambiguous, not a stranger

    out = face_enrollment.resolve_faces([_face(probe)], mem, speaker_name="Bob")

    assert mem.gallery_size(bob_pid) == 1, "ambiguous face was written into Bob's gallery"
    assert out["ambiguous"] is True
    assert out["new_face_count"] == 1


def test_ambiguous_face_is_not_stashed_for_later_naming(tmp_path):
    """With no speaker yet, an ambiguous face must not become the pending stash either —
    the next name to arrive would bind somebody else's face."""
    mem, _alice_pid, _bob_pid, probe = _two_person_gallery(tmp_path)

    out = face_enrollment.resolve_faces([_face(probe)], mem, speaker_name=None)

    assert out["pending_encoding"] is None
    assert out["ambiguous"] is True
    assert out["new_face_count"] == 1


def test_find_match_detail_reports_ambiguity_distinctly(tmp_path):
    """The matcher must be able to say 'somebody IS close, I just cannot choose'."""
    mem, _alice_pid, _bob_pid, probe = _two_person_gallery(tmp_path)

    detail = mem.find_match_detail(probe)
    assert detail["match"] is None
    assert detail["ambiguous"] is True

    stranger = np.zeros(128); stranger[0] = 9.0
    far = mem.find_match_detail(stranger)
    assert far["match"] is None
    assert far["ambiguous"] is False

    clear = mem.find_match_detail(np.zeros(128))
    assert clear["match"] is not None and clear["match"]["name"] == "Alice"
    assert clear["ambiguous"] is False


# ---------------------------------------------------------------------------
# Final-review CRITICAL 2 — "exactly one unknown face" is not enough. If the
# speaker's OWN face is already among the matched faces in the same frame, then
# that speaker is accounted for and the unknown face belongs to somebody else.
# This is the doorway case main.py already greets ("And who's your friend?").
# ---------------------------------------------------------------------------


def _known_guest_plus_stranger(tmp_path):
    mem = FaceMemory(str(tmp_path / "faces.db"))
    alice = np.zeros(128)
    alice_pid = mem.learn_guest("Alice", alice)
    stranger = np.zeros(128); stranger[0] = 5.0     # far outside tolerance -> unknown
    return mem, alice_pid, alice, stranger


def test_stranger_is_not_bound_to_a_speaker_already_matched_in_frame(tmp_path):
    mem, alice_pid, alice, stranger = _known_guest_plus_stranger(tmp_path)

    out = face_enrollment.resolve_faces(
        [_face(alice), _face(stranger)], mem, speaker_name="Alice")

    assert mem.gallery_size(alice_pid) == 1, "the stranger's face was bound to Alice"
    assert mem.find_match(stranger) is None
    assert out["new_face_count"] == 1


def test_stranger_is_not_stashed_while_the_speakers_face_is_matched(tmp_path):
    """Stashing is just as dangerous here: main.py links the stash to
    state_current['speaker_name'] on the next turn, which is still Alice."""
    mem, _alice_pid, alice, stranger = _known_guest_plus_stranger(tmp_path)

    out = face_enrollment.resolve_faces(
        [_face(alice), _face(stranger)], mem, speaker_name="Alice")

    assert out["pending_encoding"] is None


def test_unknown_face_still_enrolls_when_the_speaker_is_not_in_frame(tmp_path):
    """The fix must not break the normal case: speaker known by VOICE, their face
    not yet in the gallery, one unknown face -> still enrolls."""
    mem = FaceMemory(str(tmp_path / "faces.db"))
    alice = np.zeros(128)
    mem.learn_guest("Alice", alice)
    newcomer = np.zeros(128); newcomer[0] = 5.0

    out = face_enrollment.resolve_faces([_face(newcomer)], mem, speaker_name="Bob")

    assert mem.find_match(newcomer)["name"] == "Bob"
    assert out["new_face_count"] == 0


# ---------------------------------------------------------------------------
# Final-review CRITICAL 3 — a stashed encoding must expire. Trace: guest A is
# stashed at the door and leaves without speaking; guest B arrives, every frame
# is motion-blurred so nothing new is stashed; B says "my name is Bob" and
# link_pending_face binds guest A's FACE to Bob.
# ---------------------------------------------------------------------------


def test_link_pending_face_refuses_a_stale_stash():
    fm = FakeFaceMemory()
    enc = np.arange(128, dtype=np.float64)
    stale = time.time() - (face_enrollment.PENDING_FACE_TTL_SECONDS + 1.0)
    assert face_enrollment.link_pending_face(fm, "Bob", enc, stashed_at=stale) is False
    assert fm.learned == []


def test_link_pending_face_accepts_a_fresh_stash():
    fm = FakeFaceMemory()
    enc = np.arange(128, dtype=np.float64)
    fresh = time.time() - 5.0
    assert face_enrollment.link_pending_face(fm, "Bob", enc, stashed_at=fresh) is True
    assert fm.learned[0][0] == "Bob"


def test_quality_rejected_face_is_reported_explicitly():
    """main.py must be able to branch on the quality-reject case instead of falling
    through both the 'stash' and the 'ambiguous' branches and leaving a stale stash."""
    fm = FakeFaceMemory(match_result=None)
    out = face_enrollment.resolve_faces(
        [{"encoding": _enc(1), "quality": 0.05}], fm, speaker_name="Jacob")
    assert out["quality_rejected"] is True
    assert out["pending_encoding"] is None
    assert out["ambiguous"] is False
    assert out["new_face_count"] == 1
    assert fm.learned == []


def test_quality_rejection_is_logged_with_the_measured_score(caplog):
    """Final review IMPORTANT 7: a silent refusal reads as 'Mario stopped learning
    anyone' at 2am with nothing in the log to explain it."""
    fm = FakeFaceMemory(match_result=None)
    with caplog.at_level("INFO", logger="face_enrollment"):
        face_enrollment.resolve_faces(
            [{"encoding": _enc(1), "quality": 0.05}], fm, speaker_name="Jacob")
    assert any("quality" in r.message.lower() and "0.05" in r.message
               for r in caplog.records), caplog.text


def test_presence_exit_reset_clears_the_pending_face_stash():
    """presence_exit resets speaker identity; the stashed face must go with it, or it
    outlives the guest it belongs to."""
    import main  # heavy, imported lazily so the rest of this file stays light

    saved = dict(main.state_current)
    try:
        main.state_current["speaker_name"] = "Ann"
        main.state_current["_last_face_encoding"] = np.zeros(128)
        main.state_current["_last_face_encoding_ts"] = time.time()
        main._reset_visit_state()
        assert main.state_current["speaker_name"] is None
        assert main.state_current["_last_face_encoding"] is None
        assert main.state_current["_last_face_encoding_ts"] is None
    finally:
        main.state_current.clear()
        main.state_current.update(saved)
