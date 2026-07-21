"""Stage layout math (client/stage_layout.py) — pure, no pygame."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client"))

import stage_layout


def test_zero_and_negative():
    assert stage_layout.bystander_slots(0, 1920) == []
    assert stage_layout.bystander_slots(-1, 1920) == []
    assert stage_layout.bystander_slots(3, 0) == []


def test_single_bystander_sits_left_of_center():
    slots = stage_layout.bystander_slots(1, 1000)
    assert len(slots) == 1
    assert slots[0] < 500  # odd counts favor the left band


def test_pair_flanks_both_sides():
    slots = stage_layout.bystander_slots(2, 1000)
    assert len(slots) == 2
    assert slots[0] < 500 < slots[1]


def test_six_bystanders_split_three_three_within_bands():
    w = 1920
    slots = stage_layout.bystander_slots(6, w)
    assert len(slots) == 6
    left, right = slots[:3], slots[3:]
    assert all(s < w // 2 for s in left)
    assert all(s > w // 2 for s in right)
    # Monotonic within each band, all inside the window.
    assert left == sorted(left) and right == sorted(right)
    assert all(0 < s < w for s in slots)
    assert all(isinstance(s, int) for s in slots)


def test_bystander_order_excludes_active_keeps_roster_order():
    roster = ["pomni", "jax", "ragatha", "caine"]
    assert stage_layout.bystander_order(roster, "jax") == ["pomni", "ragatha", "caine"]
    assert stage_layout.bystander_order(roster, "nobody") == roster
    assert stage_layout.bystander_order([], "jax") == []
