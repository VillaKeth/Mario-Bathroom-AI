"""Resolve a chat-typed name to a persistent speaker_id (the personal-memory key).

A typed name is a CLAIM, not proof. Personal memory is keyed on a stable hash of
the (VIP-canonicalized) name, kept separate from a VIP profile's injected memories,
so voice/face can confirm/merge later. Never raises.
"""
import hashlib
import logging

import memory
import vip_knowledge

logger = logging.getLogger(__name__)


def _name_hash(name: str) -> int:
    return int(hashlib.md5(name.lower().encode()).hexdigest()[:8], 16)


def resolve_chat_identity(name: str, client_id: str = None) -> tuple:
    """Map a typed name to (speaker_id, canonical_name). (None, "") if name blank.

    client_id is reserved for a future per-browser id / IP tiebreaker; ignored now.
    """
    if not name or not name.strip():
        return None, ""
    canonical = name.strip()
    try:
        is_v, profile = vip_knowledge.is_vip(canonical)
        if is_v and profile and profile.get("name"):
            canonical = profile["name"]
    except Exception as e:
        logger.debug(f"[CHAT_ID] is_vip failed for '{name}': {e}")
    try:
        person = memory.find_person_by_name(canonical)
        if person:
            memory.record_visit(person["id"])
            return person["id"], canonical
        pid = _name_hash(canonical)
        memory.register_person(pid, canonical)
        return pid, canonical
    except Exception as e:
        logger.warning(f"[CHAT_ID] memory resolve failed for '{canonical}': {e}")
        return _name_hash(canonical), canonical
