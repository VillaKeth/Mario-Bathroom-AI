"""Tests for the Night Progression System (14 tests)."""

import pytest
from server.night_progression import NightProgression, Phase, FALLBACK_OBSESSION_TOPICS


@pytest.fixture
def progression():
    """Fresh NightProgression instance for each test."""
    return NightProgression(start_time=0)


# --- Phase from clock ---

def test_phase_1_at_start(progression):
    """hours=0.5 → WARM_UP"""
    assert progression.get_time_phase(0.5) == Phase.WARM_UP


def test_phase_2_at_3_hours(progression):
    """hours=3.0 → PARTY_MODE"""
    assert progression.get_time_phase(3.0) == Phase.PARTY_MODE


def test_phase_3_at_6_hours(progression):
    """hours=6.0 → UNHINGED"""
    assert progression.get_time_phase(6.0) == Phase.UNHINGED


def test_phase_4_at_7_5_hours(progression):
    """hours=7.5 → WIND_DOWN"""
    assert progression.get_time_phase(7.5) == Phase.WIND_DOWN


# --- Guest energy ---

def test_guest_energy_low(progression):
    """guests=3 → energy 1"""
    assert progression.get_guest_energy(3) == 1


def test_guest_energy_medium(progression):
    """guests=10 → energy 2"""
    assert progression.get_guest_energy(10) == 2


def test_guest_energy_high(progression):
    """guests=20 → energy 3"""
    assert progression.get_guest_energy(20) == 3


# --- Effective phase (min of time + energy) ---

def test_effective_phase_capped_by_guests(progression):
    """hour 6 (UNHINGED) + 3 guests (energy 1) → capped to WARM_UP"""
    assert progression.get_effective_phase(6.0, 3) == Phase.WARM_UP


def test_effective_phase_full_party(progression):
    """hour 6 (UNHINGED) + 25 guests (energy 4) → UNHINGED"""
    assert progression.get_effective_phase(6.0, 25) == Phase.UNHINGED


# --- Prompt modifier ---

def test_prompt_modifier_has_required_keys(progression):
    """All phases must return personality_warmth, chaos, gossip_aggression, roast_level."""
    required_keys = {"personality_warmth", "chaos", "gossip_aggression", "roast_level"}
    for phase in Phase:
        modifier = progression.get_prompt_modifier(phase)
        assert set(modifier.keys()) == required_keys, f"Missing keys for {phase.name}"
        for key, val in modifier.items():
            assert 0.0 <= val <= 1.0, f"{key}={val} out of range for {phase.name}"


# --- Obsession lock ---

def test_obsession_lock_generates_topic(progression):
    """Picks from guest_topics when available."""
    topics = ["pineapple on pizza", "mushroom controversy"]
    result = progression.get_obsession_topic(topics)
    assert result in topics


def test_obsession_lock_uses_fallback(progression):
    """Empty guest_topics → uses fallback list."""
    result = progression.get_obsession_topic([])
    assert result in FALLBACK_OBSESSION_TOPICS

    result_none = progression.get_obsession_topic(None)
    assert result_none in FALLBACK_OBSESSION_TOPICS


# --- Guardrails ---

def test_guardrails_present(progression):
    """All phases must have banned_topics and max_roasts_per_guest."""
    for phase in Phase:
        guardrails = progression.get_guardrails(phase)
        assert "banned_topics" in guardrails, f"Missing banned_topics for {phase.name}"
        assert "max_roasts_per_guest" in guardrails, f"Missing max_roasts_per_guest for {phase.name}"
        assert "de_escalation_triggers" in guardrails, f"Missing de_escalation_triggers for {phase.name}"
        assert isinstance(guardrails["banned_topics"], list)
        assert isinstance(guardrails["max_roasts_per_guest"], int)
        assert isinstance(guardrails["de_escalation_triggers"], list)


# --- Crossfade ---

def test_crossfade_window(progression):
    """At 1h55m (1.917h) → transitioning from WARM_UP to PARTY_MODE."""
    hours = 1 + 55 / 60  # 1.9167h — within [1.75, 2.0) crossfade window
    blend = progression.get_phase_blend(hours)
    assert blend["transitioning"] is True
    assert blend["from_phase"] == Phase.WARM_UP
    assert blend["to_phase"] == Phase.PARTY_MODE
    assert 0.0 < blend["blend"] < 1.0
