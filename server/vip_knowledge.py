"""VIP Knowledge System — pre-loaded biographical data for special guests.

Loads rich profiles from JSON files and injects them into Qdrant (semantic
memory) so Mario has deep knowledge about VIP guests from the moment they arrive.
"""

import hashlib
import json
import logging
import os
import random
from difflib import SequenceMatcher

import memory_semantic

DEBUG_MEMORY = True
logger = logging.getLogger(__name__)

VIP_DIR = os.path.join(os.path.dirname(__file__), "data", "vip_profiles")
_loaded_profiles: dict[str, dict] = {}
_default_profile: dict | None = None


def _deterministic_vip_id(name: str) -> int:
    """Generate a deterministic negative person_id for VIP profiles.

    Negative to avoid collision with real speaker IDs. Deterministic so
    the same VIP always gets the same ID across restarts.
    """
    raw = int(hashlib.md5(name.lower().encode()).hexdigest()[:12], 16)
    return -(raw % 100000 + 1)


def load_vip_profile(profile_name: str) -> dict | None:
    """Load a VIP profile from JSON file."""
    global _default_profile
    path = os.path.join(VIP_DIR, f"{profile_name}.json")
    if not os.path.exists(path):
        logger.warning(f"VIP profile not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    # Default profiles are used as fallback for unknown guests
    if profile.get("is_default"):
        _default_profile = profile
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Loaded default guest profile: {profile['name']}")
        return None
    _loaded_profiles[profile["name"].lower()] = profile
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] Loaded VIP profile: {profile['name']}")
    return profile


def inject_vip_memories(profile: dict, person_id: int) -> int:
    """Convert a VIP profile into searchable Qdrant memories.

    Returns the number of memories injected.
    """
    if not profile:
        return 0

    name = profile["name"]
    count = 0

    # Core biographical facts
    bio_facts = [
        f"{name} is from {profile.get('hometown', 'unknown')}",
        f"{name} is {profile.get('age', '?')} years old, born {profile.get('birthday', '?')}",
    ]
    edu = profile.get("education", {})
    if edu:
        bio_facts.append(
            f"{name} is a {edu.get('major', '')} major at {edu.get('university', '')} — {edu.get('mascot', '')}"
        )
        if edu.get("honor_society"):
            bio_facts.append(f"{name} made the Honor Society — academic achiever!")

    for title in profile.get("titles", []):
        bio_facts.append(f"{name} calls himself a {title}")

    # Family — inject each member as a separate searchable memory
    family = profile.get("family", {})
    if family.get("father"):
        bio_facts.append(f"{name}'s dad is {family['father']}")
        memory_semantic.store_memory(
            person_id,
            f"{name}'s father {family['father']} raised him in {profile.get('hometown', 'Florida')}",
            memory_type="vip_profile",
        )
        count += 1
    if family.get("mother"):
        bio_facts.append(f"{name}'s mom is {family['mother']}")
        memory_semantic.store_memory(
            person_id,
            f"{name}'s mother {family['mother']} is his mom — family clearly matters to him",
            memory_type="vip_profile",
        )
        count += 1

    for fact in bio_facts:
        memory_semantic.store_memory(person_id, fact, memory_type="vip_profile")
        count += 1

    # Projects — each gets a rich entry
    for project in profile.get("projects", []):
        proj_text = (
            f"{name} built {project['name']} ({project.get('year', '?')}) — "
            f"{project['description']}"
        )
        memory_semantic.store_memory(
            person_id, proj_text, memory_type="vip_profile",
            metadata={"project_name": project["name"]},
        )
        count += 1
        if project.get("fun_fact"):
            memory_semantic.store_memory(
                person_id,
                f"Fun fact about {project['name']}: {project['fun_fact']}",
                memory_type="vip_profile",
            )
            count += 1
        for collab in project.get("collaborators", []):
            memory_semantic.store_memory(
                person_id,
                f"{name} worked on {project['name']} with {collab}",
                memory_type="vip_profile",
            )
            count += 1

    # Skills summary
    skills = profile.get("skills", {})
    if skills.get("languages"):
        memory_semantic.store_memory(
            person_id,
            f"{name} codes in: {', '.join(skills['languages'])}",
            memory_type="vip_profile",
        )
        count += 1

    # Friends
    for friend in profile.get("friends_and_collaborators", []):
        memory_semantic.store_memory(
            person_id,
            f"{name}'s collaborator: {friend}",
            memory_type="vip_profile",
        )
        count += 1

    # Personality notes
    for note in profile.get("personality_notes", []):
        memory_semantic.store_memory(person_id, note, memory_type="vip_profile")
        count += 1

    # Memorial / sensitive data — inject as multiple searchable memories
    memorial = profile.get("memorial")
    if memorial:
        mem_text = (
            f"{name}'s {memorial['relationship']} {memorial['person']} "
            f"({memorial.get('born', '?')} — {memorial.get('passed', '?')}) "
            f"passed away. {memorial.get('note', '')}"
        )
        memory_semantic.store_memory(person_id, mem_text, memory_type="vip_memorial")
        count += 1
        # Additional memorial memories for richer semantic search hits
        memory_semantic.store_memory(
            person_id,
            f"{memorial['person']} was {name}'s {memorial['relationship']} who passed in {memorial.get('passed', '?')}",
            memory_type="vip_memorial",
        )
        count += 1
        memory_semantic.store_memory(
            person_id,
            f"The party includes a moment of silence and shot dedication for {memorial['person']}",
            memory_type="vip_memorial",
        )
        count += 1

    # Appearance hints (for webcam integration)
    appearance = profile.get("appearance_hints", {})
    if appearance.get("description"):
        memory_semantic.store_memory(person_id, f"{name} appearance: {appearance['description']}", "vip_profile")
        count += 1
    if appearance.get("notes"):
        memory_semantic.store_memory(person_id, f"{name} note: {appearance['notes']}", "vip_profile")
        count += 1

    # Conversation hooks (Mario can use these)
    for hook in profile.get("mario_conversation_hooks", []):
        memory_semantic.store_memory(
            person_id,
            f"Conversation idea for {name}: {hook}",
            memory_type="vip_hook",
        )
        count += 1

    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] Injected {count} VIP memories for {name}")
    return count


def load_all_vip_profiles():
    """Load and inject all VIP profiles from the profiles directory."""
    if not os.path.exists(VIP_DIR):
        logger.info("No VIP profiles directory found, skipping")
        return
    for filename in os.listdir(VIP_DIR):
        if filename.endswith(".json"):
            profile_name = filename.replace(".json", "")
            profile = load_vip_profile(profile_name)
            if profile:
                vip_id = _deterministic_vip_id(profile["name"])
                inject_vip_memories(profile, vip_id)


def is_vip(speaker_name: str) -> tuple[bool, dict | None]:
    """Check if a speaker matches any loaded VIP profile.

    Returns (is_vip, profile) tuple.
    """
    if not speaker_name or not _loaded_profiles:
        return False, None
    name_lower = speaker_name.lower().strip()
    for key, profile in _loaded_profiles.items():
        if name_lower == key or name_lower in key or key in name_lower:
            return True, profile
        for alias in profile.get("aliases", []):
            if name_lower == alias.lower():
                return True, profile
        if SequenceMatcher(None, name_lower, key).ratio() >= 0.75:
            return True, profile
    return False, None


def get_vip_facts_for_prompt(speaker_name: str) -> list[str]:
    """Get formatted VIP facts for direct LLM prompt injection.

    Returns a list of short fact strings for the system prompt.
    Falls back to generic party guest hooks for unknown guests.
    """
    is_v, profile = is_vip(speaker_name)
    if not is_v or not profile:
        return get_default_guest_hooks()

    facts = []
    name = profile["name"]
    facts.append(f"🌟 VIP GUEST: {name}")
    facts.append(f"Born {profile.get('birthday', '?')} in {profile.get('hometown', '?')}")

    edu = profile.get("education", {})
    if edu:
        facts.append(f"{edu.get('major', '')} major at {edu.get('university', '')} — {edu.get('mascot', '')}")

    for p in profile.get("projects", [])[:3]:
        facts.append(f"Built: {p['name']} — {p['description'][:80]}")

    # Family facts — so Mario naturally references parents
    family = profile.get("family", {})
    if family.get("father") or family.get("mother"):
        parents = []
        if family.get("father"):
            parents.append(f"dad {family['father']}")
        if family.get("mother"):
            parents.append(f"mom {family['mother']}")
        facts.append(f"Family: {', '.join(parents)}")

    # Memorial awareness
    memorial = profile.get("memorial")
    if memorial:
        facts.append(
            f"❤️ {memorial['person']} ({memorial['relationship']}) passed in "
            f"{memorial.get('passed', '?')} — honor respectfully if it comes up"
        )

    for note in profile.get("personality_notes", [])[:2]:
        facts.append(note)

    hooks = profile.get("mario_conversation_hooks", [])
    if hooks:
        facts.append(f"💡 Conversation idea: {random.choice(hooks)}")

    return facts


def get_default_guest_hooks() -> list[str]:
    """Get conversation hooks from the generic party guest profile.

    Returns hints for engaging with unknown guests who don't have a VIP profile.
    """
    if not _default_profile:
        return []
    hints = []
    greeting_hints = _default_profile.get("greeting_hints", [])
    if greeting_hints:
        hints.append(f"🎉 {random.choice(greeting_hints)}")
    hooks = _default_profile.get("conversation_hooks", [])
    if hooks:
        hints.append(f"💡 Try asking: {random.choice(hooks)}")
    return hints


def get_memorial_info(speaker_name: str) -> dict | None:
    """Get memorial/moment-of-silence info for a VIP guest.

    Returns dict with person, relationship, born, passed, note or None.
    """
    is_v, profile = is_vip(speaker_name)
    if not is_v or not profile:
        return None
    return profile.get("memorial")
