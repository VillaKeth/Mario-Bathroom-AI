"""Night Progression System — Mario's personality escalates across 4 phases during an 8-hour party.

Phase 1 WARM_UP   (0-2h):  Friendly, welcoming
Phase 2 PARTY_MODE(2-5h):  Energetic, gossip-forward
Phase 3 UNHINGED  (5-7h):  Chaotic, absurd, obsession lock
Phase 4 WIND_DOWN (7-8h):  Nostalgic, sentimental callbacks
"""

import logging
import random
import time
from enum import IntEnum

logger = logging.getLogger("night-progression")

DEBUG_NIGHT = True

_CHARACTER_NAME = "Mario"
_CHARACTER_DISPLAY_NAME = "Mario"


def set_character(name: str, display_name: str):
    global _CHARACTER_NAME, _CHARACTER_DISPLAY_NAME
    if name:
        _CHARACTER_NAME = name
    if display_name:
        _CHARACTER_DISPLAY_NAME = display_name


class Phase(IntEnum):
    WARM_UP = 1
    PARTY_MODE = 2
    UNHINGED = 3
    WIND_DOWN = 4


# 20 absurd fallback obsession topics for Phase 3
FALLBACK_OBSESSION_TOPICS = [
    "whether the snack table has a secret hierarchy",
    "why party playlists peak on the fourth song",
    "the emotional meaning of a half-finished drink",
    "whether balloons can sense fear",
    "why bathroom mirrors make every conversation more dramatic",
    "the true identity of the mystery dip on the counter",
    "whether the DJ is reading everyone's mind",
    "how many people are fake-laughing versus real-laughing",
    "the social politics of calling the last slice of pizza",
    "whether the host planned this chaos or just embraced it",
    "why someone always starts a deep conversation near the sink",
    "the secret economy of borrowed phone chargers",
    "whether confetti is a decoration or a warning",
    "the statistical likelihood of two people wearing the same shoes",
    "why every party develops one incredibly specific inside joke",
    "whether the quietest guest actually knows the most gossip",
    "the moral implications of leaving one chip in the bowl",
    "why late-night snacks taste more profound after midnight",
    "whether the bathroom line is a portal to another timeline",
    "how a single song can reset the whole room's energy",
]


class NightProgression:
    """Tracks party progression and computes personality modifiers per phase."""

    def __init__(self, start_time: float = None):
        now = time.time()
        if start_time is not None:
            # Only clamp if start_time is positive (not epoch 0) and >24h old
            hours_ago = (now - start_time) / 3600
            if start_time > 0 and hours_ago > 24:
                # Stale persisted time (e.g., 578h test artifact) — reset
                if DEBUG_NIGHT:
                    logger.debug(f"[DEBUG_NIGHT] NightProgression.__init__: stale start_time detected ({hours_ago:.1f}h ago), resetting to now")
                start_time = now
        self._start_time = start_time if start_time is not None else now
        # Manual phase override set by an admin (via /control). None = automatic
        # (time + guest driven). When set, it wins over both everywhere.
        self._phase_override = None
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] NightProgression.__init__: start_time={self._start_time}")

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def phase_override(self):
        """The forced Phase, or None when running automatically."""
        return self._phase_override

    def set_phase_override(self, phase: Phase):
        """Force a specific phase (admin). Wins over time + guest energy until cleared."""
        self._phase_override = phase
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] set_phase_override: {phase.name if phase else None}")

    def clear_phase_override(self):
        """Return to automatic, time/guest-based phase progression."""
        self._phase_override = None
        if DEBUG_NIGHT:
            logger.debug("[DEBUG_NIGHT] clear_phase_override")

    def get_time_phase(self, hours_elapsed: float) -> Phase:
        """Determine phase from elapsed hours: 0-2→WARM_UP, 2-5→PARTY_MODE, 5-7→UNHINGED, 7-8→WIND_DOWN.

        A manual override (set_phase_override) short-circuits this."""
        if self._phase_override is not None:
            return self._phase_override
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_time_phase: hours_elapsed={hours_elapsed}")
        if hours_elapsed < 2:
            return Phase.WARM_UP
        elif hours_elapsed < 5:
            return Phase.PARTY_MODE
        elif hours_elapsed < 7:
            return Phase.UNHINGED
        else:
            return Phase.WIND_DOWN

    def get_guest_energy(self, unique_guests: int) -> int:
        """Map guest count to energy level 1-4: <5→1, 5-14→2, 15-24→3, 25+→4."""
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_guest_energy: unique_guests={unique_guests}")
        if unique_guests < 5:
            return 1
        elif unique_guests < 15:
            return 2
        elif unique_guests < 25:
            return 3
        else:
            return 4

    def get_effective_phase(self, hours_elapsed: float, unique_guests: int) -> Phase:
        """Effective phase = min(time_phase, guest_energy). Low turnout caps escalation.

        A manual override wins outright — a forced phase ignores the guest cap."""
        if self._phase_override is not None:
            return self._phase_override
        time_phase = self.get_time_phase(hours_elapsed)
        guest_energy = self.get_guest_energy(unique_guests)
        effective = Phase(min(int(time_phase), guest_energy))
        if DEBUG_NIGHT:
            logger.debug(
                f"[DEBUG_NIGHT] get_effective_phase: time_phase={time_phase.name}, "
                f"guest_energy={guest_energy}, effective={effective.name}"
            )
        return effective

    def get_prompt_modifier(self, phase: Phase) -> dict:
        """Return personality modifier floats for the given phase (all 0.0-1.0)."""
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_prompt_modifier: phase={phase.name}")
        modifiers = {
            Phase.WARM_UP: {
                "personality_warmth": 0.9,
                "chaos": 0.1,
                "gossip_aggression": 0.1,
                "roast_level": 0.1,
            },
            Phase.PARTY_MODE: {
                "personality_warmth": 0.6,
                "chaos": 0.4,
                "gossip_aggression": 0.6,
                "roast_level": 0.4,
            },
            Phase.UNHINGED: {
                "personality_warmth": 0.3,
                "chaos": 0.9,
                "gossip_aggression": 0.9,
                "roast_level": 0.8,
            },
            Phase.WIND_DOWN: {
                "personality_warmth": 0.8,
                "chaos": 0.2,
                "gossip_aggression": 0.3,
                "roast_level": 0.2,
            },
        }
        return modifiers.get(phase, modifiers[Phase.WARM_UP])

    def get_obsession_topic(self, guest_topics: list[str] = None) -> str:
        """Pick an obsession topic for Phase 3. Uses guest topics if available, else fallback list."""
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_obsession_topic: guest_topics={guest_topics}")
        if guest_topics:
            return random.choice(guest_topics)
        return random.choice(FALLBACK_OBSESSION_TOPICS)

    def get_guardrails(self, phase: Phase) -> dict:
        """Return safety guardrails for the given phase."""
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_guardrails: phase={phase.name}")
        guardrails = {
            Phase.WARM_UP: {
                "banned_topics": ["politics", "religion", "explicit"],
                "max_roasts_per_guest": 1,
                "de_escalation_triggers": ["uncomfortable", "stop", "too far"],
            },
            Phase.PARTY_MODE: {
                "banned_topics": ["politics", "religion", "explicit"],
                "max_roasts_per_guest": 3,
                "de_escalation_triggers": ["uncomfortable", "stop", "too far", "chill"],
            },
            Phase.UNHINGED: {
                "banned_topics": ["politics", "religion", "explicit", "personal_trauma"],
                "max_roasts_per_guest": 5,
                "de_escalation_triggers": ["uncomfortable", "stop", "too far", "chill", "enough", "relax"],
            },
            Phase.WIND_DOWN: {
                "banned_topics": ["politics", "religion", "explicit"],
                "max_roasts_per_guest": 1,
                "de_escalation_triggers": ["uncomfortable", "stop", "too far"],
            },
        }
        return guardrails.get(phase, guardrails[Phase.WARM_UP])

    def get_phase_blend(self, hours_elapsed: float) -> dict:
        """Compute crossfade blend at phase boundaries (15-minute windows).

        Returns: {transitioning: bool, from_phase: Phase, to_phase: Phase, blend: float}
        blend=0.0 means fully in from_phase, blend=1.0 means fully in to_phase.
        """
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_phase_blend: hours_elapsed={hours_elapsed}")

        boundaries = [
            (2.0, Phase.WARM_UP, Phase.PARTY_MODE),
            (5.0, Phase.PARTY_MODE, Phase.UNHINGED),
            (7.0, Phase.UNHINGED, Phase.WIND_DOWN),
        ]
        crossfade_window = 0.25  # 15 minutes = 0.25 hours

        for boundary_hour, from_phase, to_phase in boundaries:
            window_start = boundary_hour - crossfade_window
            window_end = boundary_hour
            if window_start <= hours_elapsed < window_end:
                blend = (hours_elapsed - window_start) / crossfade_window
                if DEBUG_NIGHT:
                    logger.debug(
                        f"[DEBUG_NIGHT] get_phase_blend: transitioning from {from_phase.name} "
                        f"to {to_phase.name}, blend={blend:.2f}"
                    )
                return {
                    "transitioning": True,
                    "from_phase": from_phase,
                    "to_phase": to_phase,
                    "blend": round(blend, 3),
                }

        current_phase = self.get_time_phase(hours_elapsed)
        return {
            "transitioning": False,
            "from_phase": current_phase,
            "to_phase": current_phase,
            "blend": 0.0,
        }

    def get_hours_elapsed(self) -> float:
        """Helper: compute hours elapsed since party start."""
        elapsed = max(0.0, (time.time() - self._start_time) / 3600.0)
        if DEBUG_NIGHT:
            logger.debug(f"[DEBUG_NIGHT] get_hours_elapsed: {elapsed:.2f}h")
        return elapsed
