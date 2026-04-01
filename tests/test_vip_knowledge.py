"""Tests for server/vip_knowledge.py — VIP profile loader & knowledge injection.

All tests use :memory: Qdrant to avoid file-lock conflicts with running server.
"""

import os
import sys

import pytest

# vip_knowledge.py uses bare `import memory_semantic`, so server/ must be on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import server.memory_semantic as sem

# vip_knowledge does bare `import memory_semantic`; ensure it resolves to the
# same module object as `server.memory_semantic` so fixture state is shared.
sys.modules.setdefault("memory_semantic", sem)

import server.vip_knowledge as vk


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset semantic memory and VIP caches before each test."""
    sem._client = None
    sem._embedder = None
    vk._loaded_profiles.clear()
    sem.init_semantic_memory(":memory:")
    yield
    sem._client = None
    vk._loaded_profiles.clear()


def _load_jacob() -> dict:
    """Helper: load the real Jacob Hoppenstedt profile."""
    profile = vk.load_vip_profile("jacob_hoppenstedt")
    assert profile is not None
    return profile


# ---------------------------------------------------------------------------
# 1. TestLoadVipProfile
# ---------------------------------------------------------------------------
class TestLoadVipProfile:
    def test_load_jacob_profile(self):
        """Load real profile, verify name contains 'Jacob'."""
        profile = _load_jacob()
        assert "Jacob" in profile["name"]

    def test_load_nonexistent(self):
        """Non-existent profile returns None."""
        result = vk.load_vip_profile("totally_fake_person_xyz")
        assert result is None


# ---------------------------------------------------------------------------
# 2. TestInjectVipMemories
# ---------------------------------------------------------------------------
class TestInjectVipMemories:
    def test_inject_returns_count(self):
        """inject_vip_memories returns an int > 0 for a real profile."""
        profile = _load_jacob()
        vip_id = vk._deterministic_vip_id(profile["name"])
        count = vk.inject_vip_memories(profile, vip_id)
        assert isinstance(count, int)
        assert count > 0

    def test_inject_stores_in_qdrant(self):
        """Injected memories are searchable in Qdrant."""
        profile = _load_jacob()
        vip_id = vk._deterministic_vip_id(profile["name"])
        vk.inject_vip_memories(profile, vip_id)
        results = sem.search_memories("Jacob project", person_id=vip_id)
        assert len(results) > 0

    def test_inject_empty_profile_returns_zero(self):
        """Empty/falsy profile returns 0 without crashing."""
        assert vk.inject_vip_memories({}, 1) == 0
        assert vk.inject_vip_memories(None, 1) == 0


# ---------------------------------------------------------------------------
# 3. TestIsVip
# ---------------------------------------------------------------------------
class TestIsVip:
    @pytest.fixture(autouse=True)
    def _load_profile(self):
        """Ensure Jacob's profile is loaded so is_vip can match."""
        _load_jacob()

    def test_exact_match(self):
        """Full name 'Jacob Hoppenstedt' is a VIP alias match."""
        is_v, profile = vk.is_vip("Jacob Hoppenstedt")
        assert is_v is True
        assert profile is not None

    def test_first_name_match(self):
        """First name alone 'Jacob' matches via aliases."""
        is_v, profile = vk.is_vip("Jacob")
        assert is_v is True

    def test_non_vip(self):
        """Random name returns (False, None)."""
        is_v, profile = vk.is_vip("Completely Unknown Person XYZ")
        assert is_v is False
        assert profile is None

    def test_case_insensitive(self):
        """Lowercase name still matches."""
        is_v, profile = vk.is_vip("jacob lee hoppenstedt")
        assert is_v is True

    def test_empty_name(self):
        """Empty/None name returns (False, None)."""
        assert vk.is_vip("") == (False, None)
        assert vk.is_vip(None) == (False, None)


# ---------------------------------------------------------------------------
# 4. TestGetVipFactsForPrompt
# ---------------------------------------------------------------------------
class TestGetVipFactsForPrompt:
    @pytest.fixture(autouse=True)
    def _load_profile(self):
        _load_jacob()

    def test_returns_facts_list(self):
        """Returns a non-empty list of strings."""
        facts = vk.get_vip_facts_for_prompt("Jacob Hoppenstedt")
        assert isinstance(facts, list)
        assert len(facts) > 0
        assert all(isinstance(f, str) for f in facts)

    def test_facts_contain_real_info(self):
        """Facts mention known biographical details."""
        facts = vk.get_vip_facts_for_prompt("Jacob Hoppenstedt")
        combined = " ".join(facts)
        assert "Florida" in combined or "Saint Petersburg" in combined
        assert "VIP" in combined

    def test_non_vip_returns_empty(self):
        """Unknown name returns empty list."""
        facts = vk.get_vip_facts_for_prompt("Random Stranger XYZ")
        assert facts == []


# ---------------------------------------------------------------------------
# 5. TestGetMemorialInfo
# ---------------------------------------------------------------------------
class TestGetMemorialInfo:
    @pytest.fixture(autouse=True)
    def _load_profile(self):
        _load_jacob()

    def test_returns_memorial(self):
        """Jacob's profile has Lisa Webb memorial."""
        memorial = vk.get_memorial_info("Jacob Hoppenstedt")
        assert memorial is not None
        assert memorial["person"] == "Lisa Webb"
        assert "aunt" in memorial["relationship"].lower()

    def test_non_vip_returns_none(self):
        """Unknown name returns None."""
        assert vk.get_memorial_info("Random Stranger XYZ") is None


# ---------------------------------------------------------------------------
# 6. TestLoadAllVipProfiles
# ---------------------------------------------------------------------------
class TestLoadAllVipProfiles:
    def test_load_all_populates_cache(self):
        """load_all_vip_profiles populates _loaded_profiles."""
        vk.load_all_vip_profiles()
        assert len(vk._loaded_profiles) >= 1
        # Jacob should be in there
        found = any("jacob" in k for k in vk._loaded_profiles)
        assert found
