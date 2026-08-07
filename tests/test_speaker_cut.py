"""Speaker camera-cut decision logic (client/group_cut.py) — pure, no pygame."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client"))

import group_cut


def test_defer_only_group_lines():
    assert group_cut.should_defer({"speaker_id": "pomni"}) is True
    assert group_cut.should_defer({"speaker": "Pomni"}) is False  # display name alone is not a group line
    assert group_cut.should_defer({}) is False
    assert group_cut.should_defer(None) is False


def test_cut_plan_switches_to_cached_speaker():
    cache = {"jax": {"sprites": {"idle": "jax-idle"}}}
    apply, entry = group_cut.cut_plan(cache, current_id="pomni", speaker_id="jax")
    assert apply is True
    assert entry["sprites"]["idle"] == "jax-idle"


def test_cut_plan_no_op_for_same_speaker():
    cache = {"jax": {"sprites": {}}}
    apply, entry = group_cut.cut_plan(cache, current_id="jax", speaker_id="jax")
    assert apply is False and entry is None


def test_cut_plan_missing_member_keeps_current_sprites():
    apply, entry = group_cut.cut_plan({}, current_id="pomni", speaker_id="ragatha")
    assert apply is False and entry is None


def test_cut_plan_handles_empty_cache_and_id():
    assert group_cut.cut_plan(None, "pomni", "jax") == (False, None)
    assert group_cut.cut_plan({"jax": {}}, "pomni", None) == (False, None)
