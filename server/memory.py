"""Memory system for remembering people and conversations."""

import sqlite3
import os
import json
import logging
import re
from datetime import datetime

DEBUG_MEMORY = True
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.db")


def init_memory():
    """Initialize the memory database."""
    if DEBUG_MEMORY:
        logger.info("[DEBUG_MEMORY] init_memory: START")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            visit_count INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            fact TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES people(id)
        );
    """)
    conn.commit()
    conn.close()

    if DEBUG_MEMORY:
        logger.info("[DEBUG_MEMORY] init_memory: END")


def register_person(speaker_id: int, name: str):
    """Register a new person in memory (linked to their speaker ID)."""
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] register_person: id={speaker_id} name={name}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO people (id, name) VALUES (?, ?)",
        (speaker_id, name),
    )
    conn.commit()
    conn.close()


def record_visit(person_id: int):
    """Record that a person visited the bathroom."""
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] record_visit: person_id={person_id}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE people SET visit_count = visit_count + 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
        (person_id,),
    )
    conn.commit()
    conn.close()


def save_conversation(person_id: int, role: str, content: str):
    """Save a conversation line."""
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] save_conversation: person={person_id} role={role} content='{content[:50]}'")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO conversations (person_id, role, content) VALUES (?, ?, ?)",
            (person_id, role, content),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"save_conversation failed: {e}")
    finally:
        conn.close()


def save_fact(person_id: int, fact: str):
    """Save a fact learned about a person (deduplicates — won't store the same fact twice)."""
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] save_fact: person={person_id} fact='{fact}'")

    try:
        conn = sqlite3.connect(DB_PATH)
        # Check for duplicate (case-insensitive)
        existing = conn.execute(
            "SELECT id FROM facts WHERE person_id = ? AND LOWER(fact) = LOWER(?)",
            (person_id, fact),
        ).fetchone()
        if existing:
            if DEBUG_MEMORY:
                logger.info(f"[DEBUG_MEMORY] save_fact: duplicate, skipping")
            return
        conn.execute(
            "INSERT INTO facts (person_id, fact) VALUES (?, ?)",
            (person_id, fact),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"save_fact failed: {e}")
    finally:
        conn.close()


def get_person_info(person_id: int) -> dict:
    """Get all info about a person."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()

        if not person:
            return None

        info = dict(person)

        # Get recent conversations (last 10)
        convos = conn.execute(
            "SELECT role, content, timestamp FROM conversations WHERE person_id = ? ORDER BY timestamp DESC LIMIT 10",
            (person_id,),
        ).fetchall()
        info["recent_conversations"] = [dict(c) for c in convos]

        # Get all facts
        facts = conn.execute(
            "SELECT fact FROM facts WHERE person_id = ?",
            (person_id,),
        ).fetchall()
        info["facts"] = [f["fact"] for f in facts]
    except Exception as e:
        logger.error(f"get_person_info failed: {e}")
        return None
    finally:
        conn.close()

    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] get_person_info: person={person_id} visits={info['visit_count']} facts={len(info['facts'])}")

    return info


def get_memories_for_context(person_id: int) -> list[str]:
    """Get formatted memories for LLM context."""
    info = get_person_info(person_id)
    if not info:
        return []

    memories = []
    memories.append(f"Their name is {info['name']}")
    memories.append(f"They've visited {info['visit_count']} time(s)")

    # Time since first met
    try:
        from datetime import datetime
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

    for fact in info["facts"]:
        memories.append(f"You learned: {fact}")

    # Include last 3 conversation lines for richer context
    if info["recent_conversations"]:
        memories.append("Recent conversation snippets:")
        for conv in info["recent_conversations"][:3]:
            role = "They said" if conv['role'] == 'user' else "You said"
            memories.append(f"  {role}: \"{conv['content'][:80]}\"")

    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] get_memories_for_context: {len(memories)} memories for person {person_id}")

    return memories


# Pre-compiled fact extraction patterns (avoid re-compiling per call)
_FACT_RE_NAME = re.compile(r"(?:my name is|call me|i'm|i am)\s+(\w+)(?:\s|$|!)")
_FACT_RE_LIKE = re.compile(r"i (?:really )?(?:like|love|enjoy|adore)\s+(.+?)(?:\.|!|$)")
_FACT_RE_HATE = re.compile(r"i (?:hate|dislike|can't stand|despise)\s+(.+?)(?:\.|!|$)")
_FACT_RE_WORK = re.compile(r"i(?:'m| am) (?:a |an )?(\w+(?:\s+\w+)?)\s*(?:by|for|at)")
_FACT_RE_FAV = re.compile(r"my favorite (\w+) is\s+(.+?)(?:\.|!|$)")
_FACT_RE_FROM = re.compile(r"i(?:'m| am) from\s+(.+?)(?:\.|!|$)")
_FACT_RE_AGE = re.compile(r"i(?:'m| am) (\d+)\s*(?:years old)?")
_FACT_RE_STUDY = re.compile(r"i(?:'m| am) studying\s+(.+?)(?:\.|!|$)")
_FACT_RE_STUDENT = re.compile(r"i(?:'m| am) a (\w+(?:\s+\w+)?)\s*(?:student|major)")
_FACT_RE_WORK_AT = re.compile(r"i (?:work|works?) (?:at|for|in)\s+(.+?)(?:\.|!|$)")
_FACT_RE_GO_TO = re.compile(r"i (?:go|goes?) to\s+(.+?)(?:\.|!|$)")
_FACT_RE_PET = re.compile(r"i (?:have|got)\s+(?:a |an )?(\w+(?:\s+\w+)?)\s*(?:named|called)\s+(\w+)")
_FACT_RE_WITH = re.compile(r"i(?:'m| am) (?:here )?with\s+(.+?)(?:\.|!|$)")
_FACT_RE_TRAVEL = re.compile(r"i (?:just )?(?:came|flew|drove) (?:from|in from)\s+(.+?)(?:\.|!|$)")
_FACT_RE_FAMILY = re.compile(r"my (\w+)'s name is\s+(\w+)")
_FACT_RE_PLAY = re.compile(r"i play\s+(.+?)(?:\.|!|$)")
_FACT_RE_FEEL = re.compile(r"i(?:'m| am) (?:feeling |pretty )?(\w+)\s*(?:today|tonight|right now)")
_FACT_RE_FRIEND = re.compile(r"my (?:best |closest )?friend(?:'s name)? is\s+(\w+)")
_FACT_RE_LIVE = re.compile(r"i (?:live|stay) (?:in|at|near)\s+(.+?)(?:\.|!|$)")
_FACT_RE_FAN = re.compile(r"(?:i'm|i am) (?:a )?(\w+) (?:fan|lover|enthusiast)")


def extract_facts(text: str) -> list[str]:
    """Extract learnable facts from user speech (simple pattern matching)."""
    facts = []
    text_lower = text.lower()

    patterns = [
        (_FACT_RE_NAME, "Their name might be {0}"),
        (_FACT_RE_LIKE, "They like {0}"),
        (_FACT_RE_HATE, "They dislike {0}"),
        (_FACT_RE_WORK, "They work as {0}"),
        (_FACT_RE_FAV, "Their favorite {0} is {1}"),
        (_FACT_RE_FROM, "They're from {0}"),
        (_FACT_RE_AGE, "They're {0} years old"),
        (_FACT_RE_STUDY, "They're studying {0}"),
        (_FACT_RE_STUDENT, "They're a {0} student"),
        (_FACT_RE_WORK_AT, "They work at {0}"),
        (_FACT_RE_GO_TO, "They go to {0}"),
        (_FACT_RE_PET, "They have a {0} named {1}"),
        (_FACT_RE_WITH, "They came with {0}"),
        (_FACT_RE_TRAVEL, "They traveled from {0}"),
        (_FACT_RE_FAMILY, "Their {0}'s name is {1}"),
        (_FACT_RE_PLAY, "They play {0}"),
        (_FACT_RE_FEEL, "They're feeling {0}"),
        (_FACT_RE_FRIEND, "Their friend is {0}"),
        (_FACT_RE_LIVE, "They live in {0}"),
        (_FACT_RE_FAN, "They're a {0} fan"),
    ]

    for compiled_re, template in patterns:
        match = compiled_re.search(text_lower)
        if match:
            groups = [g.strip() for g in match.groups() if g]
            if groups:
                fact = template.format(*groups)
                facts.append(fact)

    # Deduplicate similar facts (same template prefix)
    seen = set()
    unique_facts = []
    for fact in facts:
        key = fact.split(" ", 3)[:3]  # First 3 words as dedup key
        key_str = " ".join(key).lower()
        if key_str not in seen:
            seen.add(key_str)
            unique_facts.append(fact)

    return unique_facts
