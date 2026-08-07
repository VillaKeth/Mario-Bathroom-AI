"""Lip-flap pose selection (client/lip_flap.py) — pure, no pygame/audio."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client"))

import lip_flap


def test_quiet_closes_mouth():
    assert lip_flap.pick_pose(0.0, None, 1.0) == "speech/listening"
    assert lip_flap.pick_pose(0.01, None, 1.0) == "speech/listening"
    assert lip_flap.pick_pose(None, None, 1.0) == "speech/listening"


def test_levels_open_mouth():
    assert lip_flap.pick_pose(0.1, None, 1.0) == "speech/talking"
    assert lip_flap.pick_pose(0.29, None, 1.0) == "speech/talking"
    assert lip_flap.pick_pose(0.30, None, 1.0) == "speech/talking_excited"
    assert lip_flap.pick_pose(1.0, None, 1.0) == "speech/talking_excited"


def test_hold_prevents_strobe():
    # A loud spike right after a change keeps the previous pose until hold expires.
    assert lip_flap.pick_pose(1.0, "speech/listening", 0.05) == "speech/listening"
    assert lip_flap.pick_pose(1.0, "speech/listening", 0.2) == "speech/talking_excited"


def test_no_prev_pose_ignores_hold():
    assert lip_flap.pick_pose(0.5, None, 0.0) == "speech/talking_excited"
