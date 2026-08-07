"""Voice barge-in gate (client/barge_gate.py) — pure."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client"))

from barge_gate import BargeGate


def test_never_fires_when_not_playing():
    g = BargeGate()
    assert not any(g.update(0.9, 0.25, playing=False) for _ in range(20))


def test_quiet_echo_never_fires():
    g = BargeGate()
    fired = [g.update(0.01, 0.25, playing=True) for _ in range(40)]
    assert not any(fired)
    assert g.echo_floor > 0.0  # it learned the bleed


def test_sustained_loud_speech_fires_once_then_cools_down():
    g = BargeGate(sustain_s=0.8, cooldown_s=2.0)
    for _ in range(10):
        g.update(0.02, 0.25, playing=True)  # learn a floor
    fires = [g.update(0.5, 0.25, playing=True) for _ in range(8)]
    assert fires.count(True) == 1
    assert fires.index(True) >= 3  # needed >= 0.8s sustained (4 chunks of 0.25)


def test_brief_spike_does_not_fire():
    g = BargeGate(sustain_s=0.8)
    for _ in range(10):
        g.update(0.02, 0.25, playing=True)
    assert g.update(0.9, 0.25, playing=True) is False  # single 250ms spike
    assert g.update(0.02, 0.25, playing=True) is False  # back to echo → run reset
    assert g.update(0.9, 0.25, playing=True) is False


def test_loud_speech_does_not_train_floor():
    g = BargeGate()
    for _ in range(10):
        g.update(0.02, 0.25, playing=True)
    floor_before = g.echo_floor
    g.update(0.9, 0.25, playing=True)  # above threshold — must not learn
    assert g.echo_floor == floor_before


def test_abs_min_guards_silence_start():
    g = BargeGate()  # echo_floor starts 0 → threshold = abs_min, not 0
    assert g.threshold >= 0.015
