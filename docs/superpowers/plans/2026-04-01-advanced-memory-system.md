# Advanced Memory System — Hybrid SQLite + Qdrant Semantic Memory

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Mario's limited keyword-matching memory with a hybrid system — SQLite for structured data + Qdrant vector DB for semantic recall — so Mario can retrieve the *most relevant* memories (not just the most recent), feed 50+ rich memories into context on ULTRA hardware, and deeply remember VIP guests like Jacob Hoppenstedt.

**Architecture:** Keep SQLite (`server/data/memory.db`) as the source of truth for structured data (people, visits, game stats, emotions). Add Qdrant vector search using `fastembed` (CPU-based, no VRAM cost) to embed every conversation and fact, enabling semantic retrieval. A new `memory_semantic.py` module wraps Qdrant. The existing `memory.py` is modified to also write embeddings on save, and `get_memories_for_context()` is upgraded to query Qdrant for the top-N most relevant memories by cosine similarity to the current conversation. A new `vip_knowledge.py` module pre-loads rich biographical data for VIP guests (Jacob Hoppenstedt) into both SQLite facts and Qdrant vectors at startup.

**Tech Stack:** Python 3.10+, `qdrant-client[fastembed]` (includes fastembed + all-MiniLM-L6-v2 model), SQLite (existing), FastAPI (existing server)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `server/memory_semantic.py` | **Create** | Qdrant wrapper — init, embed, search, upsert |
| `server/vip_knowledge.py` | **Create** | Pre-loaded VIP guest profiles (Jacob Hoppenstedt data) |
| `server/memory.py` | **Modify** | Add dual-write (SQLite + Qdrant) on save_fact/save_conversation; upgrade `get_memories_for_context()` to use semantic search |
| `server/mario_prompt.py` | **Modify** | Increase memory injection from 10 to 50 items; restructure memory format |
| `server/main.py` | **Modify** | Init Qdrant on startup; pass current user text to memory retrieval for relevance scoring |
| `server/requirements.txt` | **Modify** | Add `qdrant-client[fastembed]` dependency |
| `server/data/vip_profiles/jacob_hoppenstedt.json` | **Create** | Structured JSON with all known facts about Jacob |
| `tests/test_memory_semantic.py` | **Create** | Unit tests for semantic memory |
| `tests/test_vip_knowledge.py` | **Create** | Unit tests for VIP loading |

---

## Task 1: Install Qdrant Client + Fastembed

**Files:**
- Modify: `server/requirements.txt`

- [ ] **Step 1: Add dependency**

Add to `server/requirements.txt`:
```
qdrant-client[fastembed]>=1.9.0
```

- [ ] **Step 2: Install**

Run: `pip install "qdrant-client[fastembed]>=1.9.0"`
Expected: Successful install, fastembed downloads all-MiniLM-L6-v2 on first use (~80MB)

- [ ] **Step 3: Verify import works**

Run: `python -c "from qdrant_client import QdrantClient; from fastembed import TextEmbedding; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/requirements.txt
git commit -m "feat(memory): add qdrant-client with fastembed for semantic memory

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Create Semantic Memory Module (`memory_semantic.py`)

**Files:**
- Create: `server/memory_semantic.py`
- Test: `tests/test_memory_semantic.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_semantic.py`:
```python
"""Tests for semantic memory (Qdrant vector search)."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import memory_semantic


class TestSemanticMemory:
    """Test Qdrant-backed semantic memory."""

    @classmethod
    def setup_class(cls):
        """Init with in-memory Qdrant for tests."""
        memory_semantic.init_semantic_memory(path=":memory:")

    def test_store_and_search_fact(self):
        memory_semantic.store_memory(
            person_id=1,
            text="Jacob loves building Flutter apps",
            memory_type="fact",
        )
        results = memory_semantic.search_memories(
            query="mobile app development",
            person_id=1,
            limit=5,
        )
        assert len(results) >= 1
        assert "Flutter" in results[0]["text"]

    def test_search_across_conversations(self):
        memory_semantic.store_memory(
            person_id=1,
            text="I built an earthquake survival game in Godot",
            memory_type="conversation",
        )
        memory_semantic.store_memory(
            person_id=1,
            text="My favorite food is pizza",
            memory_type="conversation",
        )
        results = memory_semantic.search_memories(
            query="game development",
            person_id=1,
            limit=5,
        )
        assert len(results) >= 1
        assert "Godot" in results[0]["text"] or "game" in results[0]["text"].lower()

    def test_search_filters_by_person(self):
        memory_semantic.store_memory(person_id=99, text="I am from Mars", memory_type="fact")
        results = memory_semantic.search_memories(query="Mars", person_id=1, limit=10)
        for r in results:
            assert r["person_id"] != 99

    def test_global_search(self):
        """Search across all guests (for gossip/party awareness)."""
        memory_semantic.store_memory(person_id=10, text="Tony loves spaghetti", memory_type="fact")
        results = memory_semantic.search_memories(query="pasta Italian food", person_id=None, limit=10)
        assert any("spaghetti" in r["text"] for r in results)

    def test_dedup_prevents_identical_entries(self):
        memory_semantic.store_memory(person_id=1, text="I like cats", memory_type="fact")
        memory_semantic.store_memory(person_id=1, text="I like cats", memory_type="fact")
        results = memory_semantic.search_memories(query="cats", person_id=1, limit=10)
        cat_results = [r for r in results if "cats" in r["text"].lower()]
        assert len(cat_results) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory_semantic.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `memory_semantic.py`**

Create `server/memory_semantic.py`:
```python
"""Semantic memory using Qdrant vector database + fastembed.

Provides semantic (meaning-based) search over all stored memories,
enabling Mario to recall relevant facts and conversations even when
exact keywords don't match.

Uses fastembed's all-MiniLM-L6-v2 (384-dim) for CPU-based embedding — 
no GPU VRAM cost. On ULTRA hardware this is negligible overhead.
"""

import hashlib
import logging
import os
from datetime import datetime

from qdrant_client import QdrantClient, models

DEBUG_MEMORY = True
logger = logging.getLogger(__name__)

_client: QdrantClient | None = None
COLLECTION_NAME = "mario_memories"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384


def init_semantic_memory(path: str | None = None):
    """Initialize Qdrant with local file storage (or in-memory for tests).
    
    Args:
        path: Directory for persistent storage, or ":memory:" for tests.
    """
    global _client
    if path == ":memory:":
        _client = QdrantClient(location=":memory:")
    else:
        db_path = path or os.path.join(os.path.dirname(__file__), "data", "qdrant_memories")
        os.makedirs(db_path, exist_ok=True)
        _client = QdrantClient(path=db_path)

    collections = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Created Qdrant collection '{COLLECTION_NAME}'")
    else:
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] Qdrant collection '{COLLECTION_NAME}' already exists")


def _text_hash(text: str, person_id: int) -> str:
    """Deterministic ID from text + person to prevent duplicates."""
    return hashlib.md5(f"{person_id}:{text.strip().lower()}".encode()).hexdigest()


def store_memory(person_id: int, text: str, memory_type: str = "fact",
                 metadata: dict | None = None):
    """Embed and store a memory in Qdrant.
    
    Args:
        person_id: Guest identifier
        text: The memory text to embed
        memory_type: "fact", "conversation", "vip_profile", "topic"
        metadata: Optional extra metadata
    """
    if not _client or not text or len(text.strip()) < 3:
        return
    
    point_id = _text_hash(text, person_id)
    
    # Check for duplicate
    try:
        existing = _client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
        )
        if existing:
            if DEBUG_MEMORY:
                logger.info(f"[DEBUG_MEMORY] store_memory: duplicate skipped for person={person_id}")
            return
    except Exception:
        pass  # Point doesn't exist — proceed to insert

    payload = {
        "person_id": person_id,
        "text": text,
        "memory_type": memory_type,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        payload.update(metadata)

    try:
        _client.add(
            collection_name=COLLECTION_NAME,
            documents=[text],
            ids=[point_id],
            metadata=[payload],
        )
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] store_memory: stored '{text[:50]}' for person={person_id}")
    except Exception as e:
        logger.error(f"store_memory failed: {e}")


def search_memories(query: str, person_id: int | None = None,
                    limit: int = 20, score_threshold: float = 0.25) -> list[dict]:
    """Search memories by semantic similarity.
    
    Args:
        query: The search text (e.g. current user message)
        person_id: Filter to this guest only. None = search all guests.
        limit: Max results to return
        score_threshold: Minimum cosine similarity (0-1)
    
    Returns:
        List of dicts with keys: text, person_id, memory_type, score, timestamp
    """
    if not _client or not query or len(query.strip()) < 3:
        return []

    query_filter = None
    if person_id is not None:
        query_filter = models.Filter(
            must=[models.FieldCondition(
                key="person_id",
                match=models.MatchValue(value=person_id),
            )]
        )

    try:
        results = _client.query(
            collection_name=COLLECTION_NAME,
            query_text=query,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        
        memories = []
        for point in results:
            payload = point.metadata if hasattr(point, 'metadata') else point.payload
            memories.append({
                "text": payload.get("text", ""),
                "person_id": payload.get("person_id"),
                "memory_type": payload.get("memory_type", "unknown"),
                "score": point.score if hasattr(point, 'score') else 0.0,
                "timestamp": payload.get("timestamp", ""),
            })
        
        if DEBUG_MEMORY:
            logger.info(f"[DEBUG_MEMORY] search_memories: query='{query[:40]}' person={person_id} results={len(memories)}")
        return memories

    except Exception as e:
        logger.error(f"search_memories failed: {e}")
        return []


def get_collection_stats() -> dict:
    """Return stats about the semantic memory collection."""
    if not _client:
        return {"status": "not_initialized"}
    try:
        info = _client.get_collection(COLLECTION_NAME)
        return {
            "total_points": info.points_count,
            "vectors_count": info.vectors_count,
            "status": str(info.status),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_memory_semantic.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/memory_semantic.py tests/test_memory_semantic.py
git commit -m "feat(memory): add semantic memory module with Qdrant vector search

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Create VIP Knowledge Module + Jacob's Profile

**Files:**
- Create: `server/data/vip_profiles/jacob_hoppenstedt.json`
- Create: `server/vip_knowledge.py`
- Test: `tests/test_vip_knowledge.py`

- [ ] **Step 1: Create Jacob's profile JSON**

Create `server/data/vip_profiles/jacob_hoppenstedt.json`:
```json
{
  "name": "Jacob Hoppenstedt",
  "aliases": ["Jacob", "Jake"],
  "birthday": "2004-03-10",
  "age": 22,
  "hometown": "Saint Petersburg, Florida",
  "state": "Florida",
  "education": {
    "university": "University of Florida",
    "mascot": "Go Gators!",
    "major": "Computer Science",
    "honor_society": true
  },
  "titles": ["Software Engineer", "Digital Innovator", "Web Designer"],
  "contact": {
    "email": "jacobhoppenstedt@gmail.com",
    "linkedin": "linkedin.com/in/jacob-hoppenstedt",
    "github": "github.com/JacobHoppenstedt",
    "portfolio": "jacobhoppenstedt.github.io"
  },
  "projects": [
    {
      "name": "GatorCommunities (CanvasCommunities)",
      "year": 2026,
      "tech": ["TypeScript", "Next.js", "PostgreSQL", "Python", "Docker", "Prisma"],
      "description": "Campus club discovery platform with ML recommendation engine using Jaccard similarity and EASE collaborative filtering. His most recent and most starred GitHub project.",
      "fun_fact": "Uses actual machine learning to match students with clubs — not just a search bar!"
    },
    {
      "name": "CelebMax",
      "year": 2025,
      "tech": ["JavaScript", "Go", "Python", "Docker", "HairFastGAN-AI"],
      "description": "Celebrity lookalike web app — upload a photo, AI matches against 25,000 celebrity images, then applies their hairstyle to your photo using HairFastGAN.",
      "collaborators": ["Daniel Dovale", "Rohith Vellore", "Veeraj Reddy Talasani"],
      "fun_fact": "Trained on 25,000 celebrities — your face in, famous hair out!"
    },
    {
      "name": "Sweat Smart",
      "year": 2024,
      "tech": ["Flutter", "Dart", "Firebase", "ChatGPT API"],
      "description": "Workout planner mobile app that uses ChatGPT to personalize exercise routines. Cross-platform Flutter build.",
      "collaborators": ["Daniel Dovale"],
      "fun_fact": "ChatGPT as your personal trainer — now THAT'S innovation!"
    },
    {
      "name": "Profiteer",
      "year": 2024,
      "tech": ["MERN stack", "JavaScript", "D3.js", "MongoDB"],
      "description": "Financial analytics platform visualizing spending history and savings goals with beautiful D3 charts. Led front-end improvements and Scrum ceremonies.",
      "collaborators": ["Drewski2222"],
      "fun_fact": "Turns your messy spending into fancy charts — like a financial makeover show!"
    },
    {
      "name": "Normal Weather",
      "year": 2024,
      "tech": ["Godot", "C#"],
      "description": "Earthquake-preparedness survival game. Choice-driven gameplay with state machines, physics/collision, inventory, HUD. Optimized to improve FPS by 25%. Shipped for Web and desktop.",
      "collaborators": ["JonKissil"],
      "fun_fact": "A game about EARTHQUAKES called 'Normal Weather' — the irony is chef's kiss!"
    },
    {
      "name": "ImHungry",
      "year": 2023,
      "tech": ["Python", "PySimpleGUI"],
      "description": "Recipe discovery app with 10,000+ recipes. Input your ingredients, get recipe suggestions sorted by rating or time.",
      "collaborators": ["Eric Hengber", "Aryeh Bloom"],
      "fun_fact": "10,000 recipes and STILL somehow hard to decide what to eat — relatable!"
    }
  ],
  "skills": {
    "languages": ["TypeScript", "JavaScript", "Python", "Go", "C#", "Dart", "HTML", "CSS"],
    "frameworks": ["Next.js", "Flutter", "MERN stack", "Godot engine", "FastAPI"],
    "tools": ["Docker", "PostgreSQL", "Firebase", "Prisma", "SQLAlchemy", "D3.js"],
    "concepts": ["Machine Learning", "Microservices", "Scrum", "Collaborative Filtering", "AI/ML APIs"]
  },
  "friends_and_collaborators": [
    "Daniel Dovale (Sweat Smart, CelebMax — frequent collaborator)",
    "Rohith Vellore (CelebMax)",
    "Veeraj Reddy Talasani (CelebMax)",
    "Eric Hengber (ImHungry)",
    "Aryeh Bloom (ImHungry)",
    "JonKissil (Normal Weather)"
  ],
  "personality_notes": [
    "Cross-platform web and app designer with a passion for making impactful technology",
    "Florida boy his whole life — true sunshine state kid",
    "Academic achiever — Honor Society member",
    "Loves building things that help people — recipe apps, workout planners, financial tools",
    "His best friend built the Mario AI bathroom bot just for his birthday party — that's real friendship!"
  ],
  "mario_conversation_hooks": [
    "Ask about GatorCommunities — it's his latest and proudest project",
    "Reference the 'Normal Weather' earthquake game name — the irony is funny",
    "Ask if CelebMax ever matched HIM with a celebrity — who does he look like?",
    "Joke that Profiteer should help Mario manage his coin collection",
    "Reference ImHungry and ask what 10,000 recipes taught him about cooking",
    "Ask about his UF classes — what's he studying this semester?",
    "Tease him about having a Go backend AND a Python backend — pick a language, Jacob!",
    "Reference his collaborators — 'Daniel Dovale seems like your Luigi!'",
    "Ask about Flutter — does he prefer mobile or web development?",
    "Birthday callback — this whole party bot exists because of him!"
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_vip_knowledge.py`:
```python
"""Tests for VIP knowledge loading."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
import memory_semantic
import vip_knowledge


class TestVIPKnowledge:

    @classmethod
    def setup_class(cls):
        memory_semantic.init_semantic_memory(path=":memory:")

    def test_load_profile_returns_data(self):
        profile = vip_knowledge.load_vip_profile("jacob_hoppenstedt")
        assert profile is not None
        assert profile["name"] == "Jacob Hoppenstedt"
        assert len(profile["projects"]) >= 5

    def test_inject_into_qdrant(self):
        profile = vip_knowledge.load_vip_profile("jacob_hoppenstedt")
        count = vip_knowledge.inject_vip_memories(profile, person_id=1)
        assert count > 10  # Should inject many memories

    def test_searchable_after_inject(self):
        results = memory_semantic.search_memories(
            query="earthquake survival game",
            person_id=1,
            limit=5,
        )
        assert any("Normal Weather" in r["text"] or "earthquake" in r["text"].lower() for r in results)

    def test_conversation_hooks_injected(self):
        results = memory_semantic.search_memories(
            query="what projects has Jacob built",
            person_id=1,
            limit=10,
        )
        assert len(results) >= 3

    def test_get_all_vip_facts_for_prompt(self):
        facts = vip_knowledge.get_vip_facts_for_prompt("Jacob")
        assert len(facts) >= 5
        assert any("Florida" in f or "Gators" in f for f in facts)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_vip_knowledge.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `vip_knowledge.py`**

Create `server/vip_knowledge.py`:
```python
"""VIP Knowledge System — pre-loaded biographical data for special guests.

Loads rich profiles from JSON files and injects them into both SQLite
(as facts) and Qdrant (as searchable embeddings) so Mario has deep
knowledge about VIP guests from the moment they arrive.
"""

import json
import logging
import os
from difflib import SequenceMatcher

import memory_semantic

DEBUG_MEMORY = True
logger = logging.getLogger(__name__)

VIP_DIR = os.path.join(os.path.dirname(__file__), "data", "vip_profiles")
_loaded_profiles: dict[str, dict] = {}


def load_vip_profile(profile_name: str) -> dict | None:
    """Load a VIP profile from JSON file."""
    path = os.path.join(VIP_DIR, f"{profile_name}.json")
    if not os.path.exists(path):
        logger.warning(f"VIP profile not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        profile = json.load(f)
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
                # Use a deterministic person_id for VIP (negative to avoid collision)
                vip_id = -abs(hash(profile["name"]) % 100000)
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
    """
    is_v, profile = is_vip(speaker_name)
    if not is_v or not profile:
        return []

    facts = []
    name = profile["name"]
    facts.append(f"🌟 VIP GUEST: {name}")
    facts.append(f"Born {profile.get('birthday', '?')} in {profile.get('hometown', '?')}")

    edu = profile.get("education", {})
    if edu:
        facts.append(f"{edu.get('major', '')} major at {edu.get('university', '')} — {edu.get('mascot', '')}")

    for p in profile.get("projects", [])[:3]:  # Top 3 projects
        facts.append(f"Built: {p['name']} — {p['description'][:80]}")

    for note in profile.get("personality_notes", [])[:2]:
        facts.append(note)

    hooks = profile.get("mario_conversation_hooks", [])
    if hooks:
        import random
        facts.append(f"💡 Conversation idea: {random.choice(hooks)}")

    return facts
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_vip_knowledge.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/vip_knowledge.py server/data/vip_profiles/jacob_hoppenstedt.json tests/test_vip_knowledge.py
git commit -m "feat(memory): add VIP knowledge system with Jacob Hoppenstedt profile

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Upgrade `memory.py` to Dual-Write (SQLite + Qdrant)

**Files:**
- Modify: `server/memory.py`

- [ ] **Step 1: Add import and dual-write to `save_fact()`**

At the top of `memory.py`, after existing imports, add:
```python
try:
    import memory_semantic
    _HAS_SEMANTIC = True
except ImportError:
    _HAS_SEMANTIC = False
```

In `save_fact()`, after the SQLite insert succeeds (after `conn.commit()` on line 177), add:
```python
        if _HAS_SEMANTIC:
            memory_semantic.store_memory(person_id, fact, memory_type="fact")
```

- [ ] **Step 2: Add dual-write to `save_conversation()`**

In `save_conversation()`, after the SQLite insert succeeds (after `conn.commit()` on line 152), add:
```python
        if _HAS_SEMANTIC and role == "user" and len(content) > 10:
            memory_semantic.store_memory(person_id, content, memory_type="conversation")
```

Only index user messages (not Mario's responses) to avoid bloating the index with generated text.

- [ ] **Step 3: Upgrade `get_memories_for_context()` for semantic search**

Replace the current `get_memories_for_context()` function (lines 221-257) with:
```python
def get_memories_for_context(person_id: int, current_text: str = "") -> list[str]:
    """Get formatted memories for LLM context.
    
    Uses semantic search (Qdrant) when available for relevance-ranked recall,
    falling back to SQLite-only retrieval when Qdrant is unavailable.
    
    Args:
        person_id: The guest's ID
        current_text: What the user just said (for semantic relevance ranking)
    """
    info = get_person_info(person_id)
    if not info:
        return []

    memories = []
    memories.append(f"Their name is {info['name']}")
    memories.append(f"They've visited {info['visit_count']} time(s)")

    # Time since first met
    try:
        first = datetime.fromisoformat(info['first_seen'])
        diff = datetime.now() - first
        if diff.days > 0:
            memories.append(f"You first met them {diff.days} day(s) ago")
        elif diff.seconds > 3600:
            memories.append(f"You first met them {diff.seconds // 3600} hour(s) ago")
        else:
            memories.append(f"You just met them recently")
    except Exception:
        memories.append(f"First met: {info['first_seen']}")

    # Always include ALL stored facts (these are curated, not verbose)
    for fact in info["facts"]:
        memories.append(f"You learned: {fact}")

    # Semantic search for relevant memories (if available and user said something)
    if _HAS_SEMANTIC and current_text and len(current_text) > 5:
        try:
            semantic_results = memory_semantic.search_memories(
                query=current_text,
                person_id=person_id,
                limit=30,
                score_threshold=0.3,
            )
            # Add semantic matches that aren't already in facts
            existing_texts = {f.lower() for f in info["facts"]}
            for result in semantic_results:
                text = result["text"]
                if text.lower() not in existing_texts and len(text) > 10:
                    score_pct = int(result.get("score", 0) * 100)
                    memories.append(f"[Relevant memory, {score_pct}% match]: {text[:200]}")
                    existing_texts.add(text.lower())
        except Exception as e:
            logger.error(f"Semantic memory search failed, using SQLite fallback: {e}")

    # Include recent conversation snippets (last 15 for richer context on ULTRA hardware)
    if info["recent_conversations"]:
        memories.append("Recent conversation snippets:")
        for conv in info["recent_conversations"][:15]:
            role = "They said" if conv['role'] == 'user' else "You said"
            memories.append(f"  {role}: \"{conv['content'][:200]}\"")

    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] get_memories_for_context: {len(memories)} memories for person {person_id}")

    return memories
```

- [ ] **Step 4: Run existing tests to verify nothing is broken**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: All existing tests still pass

- [ ] **Step 5: Commit**

```bash
git add server/memory.py
git commit -m "feat(memory): dual-write to SQLite + Qdrant, semantic search in get_memories_for_context

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Upgrade `mario_prompt.py` Memory Injection (10 → 50 items)

**Files:**
- Modify: `server/mario_prompt.py` (line 170)

- [ ] **Step 1: Increase memory cap from 10 to 50**

Replace line 170:
```python
        memory_text = "Remember: " + "; ".join(memories[:10])
```
with:
```python
        memory_text = "Remember: " + "; ".join(memories[:50])
```

On ULTRA hardware with a 70B model, the context window is huge. 50 memory items is well within budget.

- [ ] **Step 2: Verify no other memory caps exist**

Search for other `[:10]` caps in `mario_prompt.py` that may need adjustment. Only the one on line 170 applies to memory injection.

- [ ] **Step 3: Commit**

```bash
git add server/mario_prompt.py
git commit -m "feat(memory): increase LLM memory injection cap from 10 to 50 items

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Wire Up in `main.py` — Init, Startup, and Pass Current Text

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Add imports near top (after `import memory` on line 39)**

Add:
```python
import memory_semantic
import vip_knowledge
```

- [ ] **Step 2: Initialize Qdrant + VIP profiles at startup**

In the startup section (near line 471 where `memory.init_memory()` is called), add after it:
```python
    # Initialize semantic memory (Qdrant vector DB)
    try:
        memory_semantic.init_semantic_memory()
        logger.info("Semantic memory (Qdrant) initialized")
    except Exception as e:
        logger.warning(f"Semantic memory init failed (falling back to SQLite-only): {e}")

    # Load VIP guest profiles into semantic memory
    try:
        vip_knowledge.load_all_vip_profiles()
        logger.info("VIP profiles loaded into semantic memory")
    except Exception as e:
        logger.warning(f"VIP profile loading failed: {e}")
```

- [ ] **Step 3: Pass current text to `get_memories_for_context()` calls**

Update line 1664 from:
```python
            memories = memory.get_memories_for_context(state_current["speaker_id"])
```
to:
```python
            memories = memory.get_memories_for_context(state_current["speaker_id"], current_text=text)
```

Update line 2988 from:
```python
                memories = memory.get_memories_for_context(state_current["speaker_id"])
```
to:
```python
                memories = memory.get_memories_for_context(state_current["speaker_id"], current_text=state_current.get("speaker_name", ""))
```

- [ ] **Step 4: Inject VIP facts alongside birthday_vip context**

Near line 1680, after the `birthday_vip.is_birthday_person()` check, add VIP knowledge injection:
```python
        # VIP knowledge — inject rich biographical data for known VIPs
        is_v, vip_profile = vip_knowledge.is_vip(state_current.get("speaker_name", ""))
        if is_v:
            vip_facts = vip_knowledge.get_vip_facts_for_prompt(state_current["speaker_name"])
            if vip_facts:
                ctx.append({"role": "system", "content": "🌟 VIP KNOWLEDGE: " + "; ".join(vip_facts)})
```

Also do the same near line 2992 for the greeting path.

- [ ] **Step 5: Re-inject VIP memories when VIP person_id is detected**

In the greeting handler (near line 2956 where `register_person` is called), when a VIP is detected and registered, link their VIP memories to their actual person_id:
```python
                # If VIP guest, inject their profile memories under their real person_id
                is_v, vip_profile = vip_knowledge.is_vip(state_current["speaker_name"])
                if is_v and vip_profile:
                    vip_knowledge.inject_vip_memories(vip_profile, state_current["speaker_id"])
```

- [ ] **Step 6: Add semantic memory stats to /health endpoint**

Wherever the health endpoint returns component stats, add:
```python
        "semantic_memory": memory_semantic.get_collection_stats(),
```

- [ ] **Step 7: Test the full startup flow**

Run the server and verify:
1. Server starts without errors
2. `/health` endpoint shows semantic_memory stats
3. Qdrant collection is created with VIP data points

- [ ] **Step 8: Commit**

```bash
git add server/main.py
git commit -m "feat(memory): wire Qdrant + VIP knowledge into server startup and response pipeline

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Backfill Existing SQLite Memories into Qdrant

**Files:**
- Modify: `server/memory_semantic.py` (add backfill function)
- Modify: `server/main.py` (call on startup)

- [ ] **Step 1: Add backfill function to `memory_semantic.py`**

```python
def backfill_from_sqlite():
    """One-time migration: copy existing SQLite facts and conversations into Qdrant.
    
    Safe to run multiple times — deduplication prevents double-inserts.
    """
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), "data", "memory.db")
    if not os.path.exists(db_path):
        logger.info("No SQLite memory DB found, skipping backfill")
        return 0
    
    conn = sqlite3.connect(db_path)
    count = 0
    
    # Backfill facts
    facts = conn.execute("SELECT person_id, fact FROM facts").fetchall()
    for person_id, fact in facts:
        store_memory(person_id, fact, memory_type="fact")
        count += 1
    
    # Backfill user conversations (skip Mario's responses)
    convos = conn.execute(
        "SELECT person_id, content FROM conversations WHERE role = 'user' AND LENGTH(content) > 10"
    ).fetchall()
    for person_id, content in convos:
        store_memory(person_id, content, memory_type="conversation")
        count += 1
    
    conn.close()
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] Backfilled {count} memories from SQLite to Qdrant")
    return count
```

- [ ] **Step 2: Call backfill on startup in `main.py`**

After `memory_semantic.init_semantic_memory()`, add:
```python
    # Backfill existing memories into Qdrant (idempotent)
    try:
        backfilled = memory_semantic.backfill_from_sqlite()
        if backfilled > 0:
            logger.info(f"Backfilled {backfilled} existing memories into semantic search")
    except Exception as e:
        logger.warning(f"Backfill failed (non-critical): {e}")
```

- [ ] **Step 3: Commit**

```bash
git add server/memory_semantic.py server/main.py
git commit -m "feat(memory): backfill existing SQLite memories into Qdrant on startup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Update Config + Documentation

**Files:**
- Modify: `config.json` (add Jacob's last name)

- [ ] **Step 1: Update config.json birthday_person_name**

Change `"birthday_person_name": "Jacob"` to include the full name awareness. No change needed here actually — the VIP system handles full name matching via aliases. But ensure the config fact array references "Jacob Hoppenstedt" consistently.

- [ ] **Step 2: Update `.claude/CLAUDE.md` with new memory architecture**

Add a section documenting:
- Hybrid SQLite + Qdrant memory system
- VIP knowledge profiles in `server/data/vip_profiles/`
- Semantic search via fastembed (all-MiniLM-L6-v2, 384-dim, CPU)
- Memory injection now 50 items (was 10)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: update architecture docs for hybrid memory system

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Summary

After all 8 tasks, Mario's memory goes from:
- **Before:** 10 keyword-matched memories, simple regex fact extraction, 500-conversation cap
- **After:** 50+ semantically-ranked memories, Qdrant vector search over all conversations and facts, rich VIP biographical profiles, global cross-guest search for gossip, backfilled existing data, zero GPU VRAM cost (fastembed runs on CPU)

Jacob Hoppenstedt gets ~50+ pre-loaded memory entries covering his projects, skills, collaborators, personality, and conversation hooks — Mario will know him inside and out from the moment he walks in.
