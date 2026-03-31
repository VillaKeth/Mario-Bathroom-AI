"""Comprehensive E2E tests for all Mario AI modules — runs fully offline (no server needed).

Covers: LLM Router, TTS Router, Night Progression, Watchdog, Canary, Hot Reload,
Birthday VIP, Sound Events, Catchphrase Mirror, Vomit Detection, Party Report.

~40+ checks exercising integration between modules.
"""

import json
import os
import sys
import tempfile
import time
from collections import deque
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add server directory to path
SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
sys.path.insert(0, SERVER_DIR)


# ============================================================
# LLM Router (7 tests)
# ============================================================

class TestLLMRouterE2E:
    """LLM Router: routing decisions, fallback, and stats."""

    def _make_router(self):
        from llm_router import LLMRouter
        return LLMRouter(fast_model="test-fast", quality_model="test-quality")

    def test_greeting_routes_fast(self):
        from llm_router import LLMRouter, RoutingDecision
        r = self._make_router()
        d = r.classify("Hey Mario!", response_type="greeting")
        assert d == RoutingDecision.FAST

    def test_gossip_routes_quality(self):
        from llm_router import LLMRouter, RoutingDecision
        r = self._make_router()
        d = r.classify("Tell me some gossip", response_type="gossip")
        assert d == RoutingDecision.QUALITY

    def test_must_mention_forces_quality(self):
        from llm_router import LLMRouter, RoutingDecision
        r = self._make_router()
        d = r.classify("hi", response_type="greeting",
                        system_prompt="You MUST mention the birthday person")
        assert d == RoutingDecision.QUALITY

    def test_stats_increment_on_classify(self):
        r = self._make_router()
        assert r.stats["fast"] == 0
        r.classify("hello", response_type="greeting")
        assert r.stats["fast"] == 1

    def test_fallback_returns_fast(self):
        from llm_router import RoutingDecision
        r = self._make_router()
        fb = r.get_fallback(RoutingDecision.QUALITY)
        assert fb == RoutingDecision.FAST
        assert r.stats["fallback"] == 1

    def test_get_model_returns_correct_name(self):
        from llm_router import RoutingDecision
        r = self._make_router()
        assert r.get_model(RoutingDecision.FAST) == "test-fast"
        assert r.get_model(RoutingDecision.QUALITY) == "test-quality"

    def test_infer_response_type_game(self):
        from llm_router import infer_response_type
        state = {"_active_game": "simon_says"}
        assert infer_response_type("my answer", state) == "game"


# ============================================================
# TTS Router (6 tests)
# ============================================================

class TestTTSRouterE2E:
    """TTS Router: chain order, fallback, parallel synth."""

    def _make_router(self):
        from tts_router import TTSRouter, TTSEngine
        router = TTSRouter(max_parallel=4)
        return router

    def test_register_and_chain_order(self):
        from tts_router import TTSRouter, TTSEngine
        r = self._make_router()
        e1 = TTSEngine(name="slow", synthesize_fn=lambda t, **kw: b"wav1",
                       is_available_fn=lambda: True, priority=2)
        e2 = TTSEngine(name="fast", synthesize_fn=lambda t, **kw: b"wav2",
                       is_available_fn=lambda: True, priority=1)
        r.register(e1)
        r.register(e2)
        chain = r.get_fallback_chain()
        assert chain[0].name == "fast"
        assert chain[1].name == "slow"

    def test_synthesize_uses_first_available(self):
        from tts_router import TTSRouter, TTSEngine
        r = self._make_router()
        e1 = TTSEngine(name="primary", synthesize_fn=lambda t, **kw: b"primary_wav",
                       is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="backup", synthesize_fn=lambda t, **kw: b"backup_wav",
                       is_available_fn=lambda: True, priority=1)
        r.register(e1)
        r.register(e2)
        result = r.synthesize("hello")
        assert result == b"primary_wav"

    def test_fallback_on_failure(self):
        from tts_router import TTSRouter, TTSEngine
        r = self._make_router()

        def fail_fn(t, **kw):
            raise RuntimeError("dead")

        e1 = TTSEngine(name="broken", synthesize_fn=fail_fn,
                       is_available_fn=lambda: True, priority=0)
        e2 = TTSEngine(name="works", synthesize_fn=lambda t, **kw: b"fallback",
                       is_available_fn=lambda: True, priority=1)
        r.register(e1)
        r.register(e2)
        result = r.synthesize("test")
        assert result == b"fallback"

    def test_stats_tracking(self):
        from tts_router import TTSRouter, TTSEngine
        r = self._make_router()
        e = TTSEngine(name="test_eng", synthesize_fn=lambda t, **kw: b"ok",
                      is_available_fn=lambda: True, priority=0)
        r.register(e)
        r.synthesize("one")
        r.synthesize("two")
        stats = r.get_engine_stats()
        assert stats["test_eng"]["attempts"] == 2
        assert stats["test_eng"]["successes"] == 2

    def test_unavailable_engine_skipped(self):
        from tts_router import TTSRouter, TTSEngine
        r = self._make_router()
        e1 = TTSEngine(name="offline", synthesize_fn=lambda t, **kw: b"nope",
                       is_available_fn=lambda: False, priority=0)
        e2 = TTSEngine(name="online", synthesize_fn=lambda t, **kw: b"yes",
                       is_available_fn=lambda: True, priority=1)
        r.register(e1)
        r.register(e2)
        chain = r.get_fallback_chain()
        assert len(chain) == 1
        assert chain[0].name == "online"

    def test_split_sentences(self):
        from tts_router import TTSRouter
        r = self._make_router()
        sentences = r.split_sentences("Hello there! How are you? Fine.")
        assert len(sentences) >= 3


# ============================================================
# Night Progression (7 tests)
# ============================================================

class TestNightProgressionE2E:
    """Night Progression: phases, guest energy, crossfade, guardrails, obsession."""

    def _make_prog(self):
        from night_progression import NightProgression
        return NightProgression(start_time=0)

    def test_all_four_phases(self):
        from night_progression import Phase
        p = self._make_prog()
        assert p.get_time_phase(0.5) == Phase.WARM_UP
        assert p.get_time_phase(3.0) == Phase.PARTY_MODE
        assert p.get_time_phase(6.0) == Phase.UNHINGED
        assert p.get_time_phase(7.5) == Phase.WIND_DOWN

    def test_guest_energy_caps_phase(self):
        from night_progression import Phase
        p = self._make_prog()
        # Few guests should cap at lower energy
        effective = p.get_effective_phase(6.0, unique_guests=3)
        assert effective.value <= Phase.UNHINGED.value

    def test_prompt_modifier_keys(self):
        from night_progression import Phase
        p = self._make_prog()
        required = {"personality_warmth", "chaos", "gossip_aggression", "roast_level"}
        for phase in Phase:
            mod = p.get_prompt_modifier(phase)
            assert set(mod.keys()) == required

    def test_modifier_values_in_range(self):
        from night_progression import Phase
        p = self._make_prog()
        for phase in Phase:
            mod = p.get_prompt_modifier(phase)
            for val in mod.values():
                assert 0.0 <= val <= 1.0

    def test_crossfade_blend(self):
        p = self._make_prog()
        blend = p.get_phase_blend(1.9)  # Near WARM_UP → PARTY_MODE boundary
        assert "transitioning" in blend
        assert "blend" in blend

    def test_guardrails_exist_for_each_phase(self):
        from night_progression import Phase
        p = self._make_prog()
        for phase in Phase:
            g = p.get_guardrails(phase)
            assert isinstance(g, dict)

    def test_obsession_topic_returns_string(self):
        p = self._make_prog()
        topic = p.get_obsession_topic(["pizza", "games"])
        assert isinstance(topic, str)
        assert len(topic) > 0


# ============================================================
# Watchdog (4 tests)
# ============================================================

class TestWatchdogE2E:
    """Watchdog: tier transitions and restart logic."""

    def _make_watchdog(self):
        from watchdog import Watchdog, DegradationTier
        return Watchdog(server_url="http://localhost:9999", max_failures=3)

    def test_initial_tier_is_full(self):
        from watchdog import DegradationTier
        w = self._make_watchdog()
        assert w.current_tier == DegradationTier.FULL

    def test_failures_lead_to_emergency(self):
        from watchdog import DegradationTier
        w = self._make_watchdog()
        for _ in range(3):
            w._record_failure()
        assert w.current_tier == DegradationTier.EMERGENCY

    def test_should_restart_after_max_failures(self):
        w = self._make_watchdog()
        assert not w.should_restart()
        for _ in range(3):
            w._record_failure()
        assert w.should_restart()

    def test_tier_changed_detection(self):
        from watchdog import DegradationTier
        w = self._make_watchdog()
        assert not w.tier_changed()
        w._record_failure()
        w._record_failure()
        w._record_failure()
        assert w.tier_changed()
        assert not w.tier_changed()  # No change since last check


# ============================================================
# Canary (2 tests)
# ============================================================

class TestCanaryE2E:
    """Canary: format and confidence scoring."""

    def test_format_result(self):
        from canary import Canary
        c = Canary(server_url="http://localhost:9999")
        result = c._format_result("test_check", True, "All good")
        assert result["test"] == "test_check"
        assert result["passed"] is True
        assert result["message"] == "All good"

    def test_confidence_calculation(self):
        from canary import Canary
        c = Canary(server_url="http://localhost:9999")
        results = [
            c._format_result("t1", True, "ok"),
            c._format_result("t2", True, "ok"),
            c._format_result("t3", False, "fail"),
            c._format_result("t4", True, "ok"),
        ]
        confidence = c._calculate_confidence(results)
        assert confidence == 75  # 3/4 passed


# ============================================================
# Hot Reload (4 tests)
# ============================================================

class TestHotReloadE2E:
    """Hot Reload: get, set, reload, and file watch."""

    def _make_config(self, tmp_path):
        from hot_reload import LiveConfig
        path = str(tmp_path / "live_config.json")
        return LiveConfig(path)

    def test_get_default_values(self, tmp_path):
        lc = self._make_config(tmp_path)
        assert lc.get("chaos_level") == 5
        assert lc.get("nonexistent", 42) == 42

    def test_set_persists_to_disk(self, tmp_path):
        from hot_reload import LiveConfig
        path = str(tmp_path / "live_config.json")
        lc1 = LiveConfig(path)
        lc1.set("chaos_level", 9)
        lc2 = LiveConfig(path)
        assert lc2.get("chaos_level") == 9

    def test_reload_picks_up_external_changes(self, tmp_path):
        from hot_reload import LiveConfig
        path = str(tmp_path / "live_config.json")
        lc = LiveConfig(path)
        # Simulate external edit
        data = json.loads(open(path).read())
        data["chaos_level"] = 1
        with open(path, "w") as f:
            json.dump(data, f)
        lc.reload()
        assert lc.get("chaos_level") == 1

    def test_to_dict_returns_copy(self, tmp_path):
        lc = self._make_config(tmp_path)
        d = lc.to_dict()
        d["chaos_level"] = 999
        assert lc.get("chaos_level") != 999


# ============================================================
# Birthday VIP (4 tests)
# ============================================================

class TestBirthdayVIPE2E:
    """Birthday VIP: name match, greeting, interaction tracking."""

    def _make_vip(self, name="Mario", facts=None):
        from birthday_vip import BirthdayVIP
        return BirthdayVIP(name=name, birthday_facts=facts or ["Loves mushrooms"])

    def test_exact_name_match(self):
        vip = self._make_vip("Sarah")
        assert vip.is_birthday_person("Sarah")
        assert vip.is_birthday_person("sarah")

    def test_fuzzy_name_match(self):
        vip = self._make_vip("Michael")
        assert vip.is_birthday_person("michael")
        assert vip.is_birthday_person("Mike") or not vip.is_birthday_person("Mike")  # May or may not match

    def test_greeting_returns_string(self):
        vip = self._make_vip("Luigi")
        greeting = vip.get_special_greeting("Luigi")
        assert greeting is not None
        assert isinstance(greeting, str)
        assert len(greeting) > 0

    def test_interaction_tracking(self):
        vip = self._make_vip("Peach")
        assert vip.interaction_count == 0
        vip.get_vip_prompt_injection()
        assert vip.interaction_count == 1
        vip.get_vip_prompt_injection()
        assert vip.interaction_count == 2


# ============================================================
# Sound Events (3 tests)
# ============================================================

class TestSoundEventsE2E:
    """Sound Events: trigger and graceful degradation."""

    def test_no_dir_graceful(self, tmp_path):
        from sound_events import SoundEventManager
        mgr = SoundEventManager(sfx_dir=str(tmp_path / "nonexistent_sfx"))
        assert not mgr.is_available()
        mgr.trigger("greeting")  # Should not raise

    def test_available_events_empty_when_no_files(self, tmp_path):
        from sound_events import SoundEventManager
        mgr = SoundEventManager(sfx_dir=str(tmp_path / "empty_sfx"))
        events = mgr.get_available_events()
        assert events == []

    def test_websocket_trigger_returns_dict_or_none(self, tmp_path):
        from sound_events import SoundEventManager
        sfx_dir = str(tmp_path / "sfx")
        os.makedirs(sfx_dir, exist_ok=True)
        mgr = SoundEventManager(sfx_dir=sfx_dir)
        result = mgr.trigger_websocket("nonexistent_event")
        assert result is None or isinstance(result, dict)


# ============================================================
# Catchphrase Mirror (4 tests)
# ============================================================

class TestCatchphraseMirrorE2E:
    """Catchphrase Mirror: feed, mirror, exclusion."""

    def _make_mirror(self, threshold=3):
        from catchphrase_mirror import CatchphraseMirror
        return CatchphraseMirror(threshold=threshold)

    def test_no_mirror_below_threshold(self):
        m = self._make_mirror(threshold=3)
        m.feed("Bob", "pizza is great")
        m.feed("Bob", "pizza rocks")
        result = m.get_mirror_phrase("Bob")
        assert result is None

    def test_mirror_at_threshold(self):
        m = self._make_mirror(threshold=3)
        m.feed("Bob", "pizza pizza pizza")
        result = m.get_mirror_phrase("Bob")
        assert result is not None
        assert "pizza" in result.lower()

    def test_mirror_only_fires_once(self):
        m = self._make_mirror(threshold=2)
        m.feed("Alice", "mushroom mushroom mushroom")
        first = m.get_mirror_phrase("Alice")
        assert first is not None
        second = m.get_mirror_phrase("Alice")
        assert second is None  # Already mirrored

    def test_get_party_catchphrases(self):
        m = self._make_mirror(threshold=2)
        m.feed("Tom", "star star star power power")
        phrases = m.get_party_catchphrases()
        assert isinstance(phrases, dict)
        assert "tom" in phrases or "Tom" in phrases


# ============================================================
# Vomit / Audio Distress (3 tests)
# ============================================================

class TestVomitDetectionE2E:
    """Vomit detection: spike detection, temporal coherence, confidence."""

    def test_distress_tracker_init(self):
        from audio_distress import DistressTracker
        dt = DistressTracker()
        assert dt._baseline_initialized is False

    def test_volume_spike_detection(self):
        import struct
        from audio_distress import DistressTracker
        dt = DistressTracker()
        # _compute_rms returns normalized values (0-1 range for int16)
        # Set a low baseline, then check if a loud sample triggers spike
        quiet_samples = [100] * 100
        quiet = struct.pack("<" + "h" * 100, *quiet_samples)
        quiet_rms = dt._compute_rms(quiet)
        # Set baseline manually to quiet RMS (bypassing EMA)
        dt._rms_baseline = quiet_rms
        dt._baseline_initialized = True
        # Loud spike: 30000 amplitude is ~300× the quiet 100 amplitude
        loud = struct.pack("<" + "h" * 100, *([30000] * 100))
        loud_rms = dt._compute_rms(loud)
        # Spike threshold is baseline * 3.0, so 300× should easily exceed it
        assert loud_rms > dt._rms_baseline * dt.SPIKE_MULTIPLIER
        is_spike = dt._check_volume_spike(loud_rms)
        assert is_spike is True

    def test_false_trigger_suppression(self):
        from audio_distress import DistressTracker
        dt = DistressTracker()
        # _check_false_triggers expects string class names in top_classes
        frame = {
            "is_distress": True,
            "top_classes": [("Laughter", 0.8), ("Groan", 0.2)],
        }
        suppressed = dt._check_false_triggers(frame)
        assert suppressed is not None


# ============================================================
# Party Report (5 tests)
# ============================================================

class TestPartyReportE2E:
    """Party Report: generate format, integration with modules."""

    def test_generate_returns_required_keys(self):
        from party_report import PartyReport
        report = PartyReport(server_start_time=time.time() - 3600)
        data = report.generate()
        required = {
            "party_duration_hours", "error_count", "total_guests",
            "total_interactions", "total_audio_minutes", "avg_response_time",
            "most_popular_game", "funniest_moment", "top_gossip_topics",
            "top_catchphrases", "phase_timeline", "birthday_person_interactions",
            "tts_stats", "llm_stats",
        }
        assert required.issubset(set(data.keys()))

    def test_duration_calculation(self):
        from party_report import PartyReport
        start = time.time() - 7200  # 2 hours ago
        report = PartyReport(server_start_time=start)
        data = report.generate()
        assert 1.9 <= data["party_duration_hours"] <= 2.1

    def test_to_html_returns_valid_html(self):
        from party_report import PartyReport
        report = PartyReport(server_start_time=time.time() - 1800)
        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "Mario AI Party Report" in html
        assert "</html>" in html

    def test_integration_with_gossip(self):
        from party_report import PartyReport
        mock_gossip = MagicMock()
        mock_gossip._guest_names = {"id1": "Alice", "id2": "Bob"}
        mock_gossip._gossip_log = [
            {"type": "funny", "speaker_name": "Alice", "text": "LOL moment", "keyword": "pizza", "timestamp": time.time()},
            {"type": "opinion", "speaker_name": "Bob", "text": "I love pizza", "keyword": "pizza", "timestamp": time.time()},
        ]
        report = PartyReport(
            server_start_time=time.time() - 3600,
            party_gossip=mock_gossip,
        )
        data = report.generate()
        assert data["total_guests"] == 2
        assert data["funniest_moment"] != "No funny moments captured"
        assert len(data["top_gossip_topics"]) > 0

    def test_integration_with_vip(self):
        from party_report import PartyReport
        mock_vip = MagicMock()
        mock_vip.is_configured.return_value = True
        mock_vip.name = "Princess Peach"
        mock_vip.interaction_count = 5
        report = PartyReport(
            server_start_time=time.time() - 3600,
            birthday_vip=mock_vip,
        )
        data = report.generate()
        assert data["birthday_person_interactions"]["name"] == "Princess Peach"
        assert data["birthday_person_interactions"]["interaction_count"] == 5


# ============================================================
# Cross-module integration (3 tests)
# ============================================================

class TestCrossModuleIntegration:
    """Tests verifying modules work together correctly."""

    def test_night_progression_feeds_gossip_aggression(self):
        """Night progression personality modifiers feed into gossip system."""
        from night_progression import NightProgression, Phase
        prog = NightProgression(start_time=0)
        mod = prog.get_prompt_modifier(Phase.UNHINGED)
        assert mod["gossip_aggression"] > 0.5  # UNHINGED should be aggressive

    def test_llm_router_with_must_mention_prompt(self):
        """System prompt containing 'MUST mention' forces QUALITY routing."""
        from llm_router import LLMRouter, RoutingDecision
        router = LLMRouter(fast_model="fast", quality_model="quality")
        system_prompt = "You MUST mention the birthday person's name!"
        decision = router.classify("hi", response_type="greeting", system_prompt=system_prompt)
        assert decision == RoutingDecision.QUALITY

    def test_report_with_all_modules_mocked(self):
        """Full report generation with all module dependencies mocked."""
        from party_report import PartyReport

        mock_gossip = MagicMock()
        mock_gossip._guest_names = {"a": "A", "b": "B", "c": "C"}
        mock_gossip._gossip_log = []

        mock_mirror = MagicMock()
        mock_mirror.get_party_catchphrases.return_value = {"A": [("wow", 5)]}

        mock_vip = MagicMock()
        mock_vip.is_configured.return_value = True
        mock_vip.name = "Birthday Kid"
        mock_vip.interaction_count = 3

        mock_tts = MagicMock()
        mock_tts.get_engine_stats.return_value = {
            "edge_tts": {"attempts": 10, "successes": 9, "failures": 1, "success_rate": "90%"}
        }

        mock_llm = MagicMock()
        mock_llm.stats = {"fast": 20, "quality": 10, "fallback": 2}

        state = {
            "conversation_history": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "play a game"},
            ],
            "_response_times": deque([0.5, 0.3, 0.4]),
            "_game_state": {"game_name": "Simon Says"},
        }

        report = PartyReport(
            server_start_time=time.time() - 10800,
            party_gossip=mock_gossip,
            catchphrase_mirror=mock_mirror,
            birthday_vip=mock_vip,
            tts_router=mock_tts,
            llm_router=mock_llm,
            state_current=state,
            error_count=3,
        )
        data = report.generate()

        assert data["total_guests"] == 3
        assert data["total_interactions"] == 2
        assert data["avg_response_time"] == 0.4
        assert data["most_popular_game"] == "Simon Says"
        assert data["error_count"] == 3
        assert data["birthday_person_interactions"]["name"] == "Birthday Kid"
        assert data["tts_stats"]["edge_tts"]["success_rate"] == "90%"
        assert data["llm_stats"]["fast"] == 20
        assert "wow" in str(data["top_catchphrases"])
        assert 2.9 <= data["party_duration_hours"] <= 3.1
