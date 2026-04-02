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


# --- Boundary and edge case tests ---

@pytest.mark.parametrize("hours,expected", [
    (0.0, Phase.WARM_UP),
    (2.0, Phase.PARTY_MODE),
    (5.0, Phase.UNHINGED),
    (7.0, Phase.WIND_DOWN),
    (-1.0, Phase.WARM_UP),
    (100.0, Phase.WIND_DOWN),
])
def test_phase_boundaries(progression, hours, expected):
    """Exact boundary values and edge cases for phase calculation."""
    assert progression.get_time_phase(hours) == expected


def test_guest_energy_zero_guests(progression):
    """Zero guests should return minimum energy."""
    energy = progression.get_guest_energy(unique_guests=0)
    assert energy >= 1


def test_start_time_zero_not_replaced():
    """start_time=0 (epoch) should be preserved, not replaced with time.time()."""
    np = NightProgression(start_time=0)
    assert np.start_time == 0


# --- Edge case tests ---

class TestNightProgressionEdgeCases:
    """Edge-case tests for NightProgression boundary conditions and resilience."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.np = NightProgression(start_time=0)

    def test_exact_boundary_warm_up_to_party(self):
        """Exactly at hour 2.0 the phase flips from WARM_UP to PARTY_MODE."""
        assert self.np.get_time_phase(1.9999) == Phase.WARM_UP
        assert self.np.get_time_phase(2.0) == Phase.PARTY_MODE

    def test_exact_boundary_party_to_unhinged(self):
        """Exactly at hour 5.0 the phase flips from PARTY_MODE to UNHINGED."""
        assert self.np.get_time_phase(4.9999) == Phase.PARTY_MODE
        assert self.np.get_time_phase(5.0) == Phase.UNHINGED

    def test_exact_boundary_unhinged_to_wind_down(self):
        """Exactly at hour 7.0 the phase flips from UNHINGED to WIND_DOWN."""
        assert self.np.get_time_phase(6.9999) == Phase.UNHINGED
        assert self.np.get_time_phase(7.0) == Phase.WIND_DOWN

    def test_restart_preserves_phase(self):
        """NightProgression created with a start_time 3 hours ago should be in PARTY_MODE."""
        import time as _time
        three_hours_ago = _time.time() - (3 * 3600)
        np = NightProgression(start_time=three_hours_ago)
        hours = np.get_hours_elapsed()
        assert 2.9 <= hours <= 3.2  # allow small timing tolerance
        assert np.get_time_phase(hours) == Phase.PARTY_MODE

    def test_zero_guests_high_hours(self):
        """0 guests at 4+ hours should not crash and should cap phase to WARM_UP."""
        phase = self.np.get_effective_phase(hours_elapsed=4.0, unique_guests=0)
        assert phase == Phase.WARM_UP  # energy 1 caps to WARM_UP
        phase_late = self.np.get_effective_phase(hours_elapsed=6.5, unique_guests=0)
        assert phase_late == Phase.WARM_UP

    def test_negative_elapsed_time(self):
        """If start_time is in the future, get_hours_elapsed clamps to 0 → WARM_UP."""
        import time as _time
        future_np = NightProgression(start_time=_time.time() + 9999)
        hours = future_np.get_hours_elapsed()
        assert hours == 0.0
        assert future_np.get_time_phase(hours) == Phase.WARM_UP

    def test_very_long_party_12_hours(self):
        """After 12 hours the party should still be in WIND_DOWN without errors."""
        phase = self.np.get_time_phase(12.0)
        assert phase == Phase.WIND_DOWN
        modifier = self.np.get_prompt_modifier(phase)
        assert "personality_warmth" in modifier
        guardrails = self.np.get_guardrails(phase)
        assert "banned_topics" in guardrails

    def test_phase_string_representation(self):
        """Every Phase enum member must have a displayable .name string."""
        expected_names = {"WARM_UP", "PARTY_MODE", "UNHINGED", "WIND_DOWN"}
        actual_names = {p.name for p in Phase}
        assert actual_names == expected_names
        for p in Phase:
            assert isinstance(p.name, str) and len(p.name) > 0
