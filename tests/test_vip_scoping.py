"""VIP knowledge must belong to THIS party, and global recall must stay global.

Two independent leaks made every character open by talking about Jacob's birthday:

1. `load_all_vip_profiles()` loaded every JSON in server/data/vip_profiles/ into
   the ACTIVE CHARACTER's Qdrant collection, ungated. A Charlie party with
   birthday_person_name unset still got the full Jacob Hoppenstedt profile.

2. `get_memories_for_context` runs a second search with person_id=None, commented
   "for VIP/global knowledge" — but with no type filter it returns EVERY memory of
   EVERY guest, including other people's conversation lines, at threshold 0.35.

Observed 2026-09-11: "You know, Jacob's birthday is turning into something
magical." from a character with no connection to Jacob.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))


@pytest.fixture(scope="module")
def vk():
    import vip_knowledge as vk
    return vk


JACOB = {"name": "Jacob Lee Hoppenstedt", "aliases": ["Jacob", "Hoppy"]}
GENERIC = {"name": "Party Guest", "is_default": True}
TEMPLATE = {"name": "Party Guest Template", "_instructions": "fill this in"}


# --- which profiles are party-specific -------------------------------------

def test_a_named_person_is_not_generic(vk):
    assert vk.is_generic_profile(JACOB) is False


def test_the_default_guest_profile_is_generic(vk):
    assert vk.is_generic_profile(GENERIC) is True


def test_a_template_profile_is_generic(vk):
    assert vk.is_generic_profile(TEMPLATE) is True


# --- matching the party's guest of honour ----------------------------------

def test_profile_matches_the_birthday_person_by_full_name(vk):
    assert vk.profile_matches_person(JACOB, "Jacob Lee Hoppenstedt") is True


def test_profile_matches_the_birthday_person_by_alias(vk):
    assert vk.profile_matches_person(JACOB, "Hoppy") is True


def test_profile_match_is_case_insensitive(vk):
    assert vk.profile_matches_person(JACOB, "jacob") is True


def test_profile_does_not_match_an_unrelated_name(vk):
    assert vk.profile_matches_person(JACOB, "Charlie Kirk") is False


def test_no_birthday_person_matches_nobody(vk):
    assert vk.profile_matches_person(JACOB, None) is False


# --- the resulting allowlist -----------------------------------------------

PROFILES = {"jacob_hoppenstedt": JACOB, "generic_party_guest": GENERIC,
            "party_guests": TEMPLATE}


def test_without_a_birthday_person_only_generic_profiles_load(vk):
    """THE BUG: Jacob loaded into a party that has nothing to do with him."""
    allowed = vk.default_allowlist(PROFILES, birthday_person_name=None)
    assert "jacob_hoppenstedt" not in allowed
    assert set(allowed) == {"generic_party_guest", "party_guests"}


def test_the_birthday_persons_profile_loads_when_named(vk):
    allowed = vk.default_allowlist(PROFILES, birthday_person_name="Jacob")
    assert "jacob_hoppenstedt" in allowed


def test_an_unrelated_birthday_person_does_not_pull_in_jacob(vk):
    allowed = vk.default_allowlist(PROFILES, birthday_person_name="Someone Else")
    assert "jacob_hoppenstedt" not in allowed


# --- the unfiltered global search ------------------------------------------

def test_global_recall_is_restricted_to_shared_knowledge_types():
    """person_id=None must mean VIP/lore, not 'every memory of every guest'."""
    import memory
    types = set(memory.GLOBAL_MEMORY_TYPES)
    assert "conversation" not in types, (
        "another guest's conversation lines must not surface as global knowledge")
    assert "fact" not in types, (
        "a fact learned about one guest is not global knowledge")
    assert any(t.startswith("vip") for t in types), "VIP knowledge is the point"
