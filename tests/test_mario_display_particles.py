import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "client"
for path in (ROOT, CLIENT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from client.mario_display import MarioDisplay


@pytest.fixture
def display():
    mario_display = object.__new__(MarioDisplay)
    mario_display._particles = []
    mario_display._disco_colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 100, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]
    return mario_display


@pytest.mark.parametrize(
    ("emotion", "expected_count"),
    [
        ("excited", 8),
        ("happy", 4),
        ("surprised", 6),
        ("confused", 3),
        ("annoyed", 4),
        ("sleepy", 2),
        ("mischievous", 5),
        ("laughing", 5),
        ("loving", 6),
        ("love", 6),
        ("proud", 5),
        ("frustrated", 5),
        ("embarrassed", 3),
        ("worried", 3),
        ("bored", 2),
        ("determined", 4),
        ("sad", 3),
        ("angry", 6),
        ("nervous", 3),
        ("scared", 4),
    ],
)
def test_spawn_emotion_particles_uses_reduced_counts(display, emotion, expected_count):
    display._spawn_emotion_particles(emotion)

    assert len(display._particles) == expected_count


@pytest.mark.parametrize(
    ("effect_type", "expected_count"),
    [
        ("fire", 8),
        ("stars", 6),
        ("hearts", 5),
        ("confetti", 10),
        ("rain", 8),
        ("sparkle", 4),
        ("mushroom", 4),
        ("coins", 5),
    ],
)
def test_spawn_keyword_particles_uses_reduced_counts(display, effect_type, expected_count):
    display.spawn_keyword_particles(effect_type)

    assert len(display._particles) == expected_count


def test_spawn_confetti_defaults_to_reduced_count(display):
    display._spawn_confetti()

    assert len(display._particles) == 10


@pytest.mark.parametrize(
    "spawn_call",
    [
        lambda display: display._spawn_emotion_particles("happy"),
        lambda display: display._spawn_confetti(),
        lambda display: display.spawn_keyword_particles("sparkle"),
    ],
)
def test_particle_spawners_cap_particles_at_one_hundred(display, spawn_call):
    display._particles = [object() for _ in range(99)]

    spawn_call(display)

    assert len(display._particles) == 100
