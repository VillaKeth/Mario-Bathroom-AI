import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import chat_identity, memory, vip_knowledge

def test_non_vip_name_stable_id(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (False, None))
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    id1, name1 = chat_identity.resolve_chat_identity("Bob")
    id2, _ = chat_identity.resolve_chat_identity("bob")   # case-insensitive
    assert isinstance(id1, int)
    assert id1 == id2          # stable across case + sessions
    assert name1 == "Bob"

def test_vip_alias_normalizes_to_canonical(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (True, {"name": "Jacob Hoppenstedt"}))
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    pid, canonical = chat_identity.resolve_chat_identity("Jake")
    assert canonical == "Jacob Hoppenstedt"
    assert isinstance(pid, int)

def test_existing_person_links_no_new_id(monkeypatch):
    monkeypatch.setattr(vip_knowledge, "is_vip", lambda n: (False, None))
    monkeypatch.setattr(memory, "find_person_by_name",
                        lambda n: {"id": 999, "name": "Bob", "visit_count": 3})
    visited = []
    monkeypatch.setattr(memory, "record_visit", lambda pid: visited.append(pid))
    pid, name = chat_identity.resolve_chat_identity("Bob")
    assert pid == 999 and visited == [999]

def test_empty_name_returns_none(monkeypatch):
    assert chat_identity.resolve_chat_identity("") == (None, "")
    assert chat_identity.resolve_chat_identity("   ") == (None, "")

def test_never_raises_on_error(monkeypatch):
    def boom(n): raise RuntimeError("vip down")
    monkeypatch.setattr(vip_knowledge, "is_vip", boom)
    monkeypatch.setattr(memory, "find_person_by_name", lambda n: None)
    monkeypatch.setattr(memory, "register_person", lambda pid, name: None)
    pid, name = chat_identity.resolve_chat_identity("Bob")
    assert isinstance(pid, int) and name == "Bob"
