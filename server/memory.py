"""Memory system for remembering people and conversations."""

import sqlite3
import os
import json
import logging
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

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (person_id, role, content) VALUES (?, ?, ?)",
        (person_id, role, content),
    )
    conn.commit()
    conn.close()


def save_fact(person_id: int, fact: str):
    """Save a fact learned about a person."""
    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] save_fact: person={person_id} fact='{fact}'")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO facts (person_id, fact) VALUES (?, ?)",
        (person_id, fact),
    )
    conn.commit()
    conn.close()


def get_person_info(person_id: int) -> dict:
    """Get all info about a person."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()

    if not person:
        conn.close()
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
    memories.append(f"First met: {info['first_seen']}")

    for fact in info["facts"]:
        memories.append(f"You learned: {fact}")

    if info["recent_conversations"]:
        last = info["recent_conversations"][0]
        memories.append(f"Last conversation ({last['timestamp']}): they said \"{last['content']}\"")

    if DEBUG_MEMORY:
        logger.info(f"[DEBUG_MEMORY] get_memories_for_context: {len(memories)} memories for person {person_id}")

    return memories
