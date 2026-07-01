# Chat-Path Person Memory — Design

**Date:** 2026-07-01
**Status:** Approved (design), pre-implementation
**Baseline:** master @ latest (post screen-watch)

## Problem / Goal

A guest who chats with Rudi over the web browser and types their name (e.g. "my
name is Jacob") currently gets `speaker_name` set but **no `speaker_id`**
(`command_handlers.py:603`, the audio-less branch). Because the response pipeline
gates all recall and `save_fact`/`save_conversation` on `if speaker_id:`
(`main.py:4221`, `5409`), the bot learns nothing about typed-only guests, and its
"I'll remember you!" reply is hollow. Goal: give typed-name chatters a persistent
`speaker_id` so Rudi starts learning about (and recalling) browser chatters —
surviving restarts — reusing the memory backend that already exists.

## Non-goals

- **Not strong identification.** A typed name is a *claim*, not proof. This build
  never authenticates it. Distinguishing the real Jacob Hoppenstedt from a Jacob
  Smith is the job of voice + face recognition (future). The design stays
  low-confidence and must not bind chat-claimed identities in a way voice/face
  would have to fight.
- **No IP / browser-id now.** Deferred (see below), with the hook stubbed.
- No new memory storage — reuse `memory.py` (SQLite + Qdrant).

## Architecture

One small new module + two wire-ups (one of which DRYs existing code).

### `server/chat_identity.py` (new) — `resolve_chat_identity`

```
resolve_chat_identity(name: str, client_id: str = None) -> tuple[int, str]
```
1. **Normalize via VIP aliases:** `is_v, profile = vip_knowledge.is_vip(name)`; if a
   VIP, use `profile["name"]` as the canonical name (so "Jake" → "Jacob Hoppenstedt"
   for consistent display + recall). Else keep the typed name.
2. **Resolve id (existing logic, extracted):** `person = memory.find_person_by_name(canonical)`
   → if found, use `person["id"]` + `record_visit`; else
   `virtual_id = int(md5(canonical.lower())[:8], 16)` → `register_person(virtual_id, canonical)`.
3. Return `(speaker_id, canonical_name)`.

`client_id` is accepted but ignored for now — the reserved seam for a future
per-browser id / IP tiebreaker.

**Why name-hash (not the VIP's canonical negative-id):** keeps chat's *personal*
memory on the claimed identity, separate from the VIP profile's injected memories.
A stranger typing "Jacob Hoppenstedt" writes to `hash("jacob hoppenstedt")`, NOT the
real VIP's confirmed store — nothing for voice/face to have to un-pollute later. VIP
*profile facts* still surface read-only by name via the existing
`get_vip_facts_for_prompt(speaker_name)` path.

### Wire-up A — typed-name path (the fix)

`command_handlers.py:603` (the audio-less `else` branch of the name parser): after
setting `state["speaker_name"] = name`, call `resolve_chat_identity(name)` and set
`state["speaker_id"]` and the canonical `state["speaker_name"]`. The reply
"I'll remember you!" becomes true.

### Wire-up B — DRY `presence_enter`

Replace the inline find-or-hash block at `main.py:6008-6020` with a call to
`resolve_chat_identity(state_current["speaker_name"])`. Same behavior, one source of
truth, and presence guests now also get VIP-alias normalization for free.

## Data flow

```
"my name is Jake"  ─parse→ name="Jake"
  → resolve_chat_identity("Jake")
      is_vip → canonical="Jacob Hoppenstedt"
      find_person_by_name / hash → speaker_id
  → state speaker_id + speaker_name set
  → pipeline: get_memories_for_context(speaker_id) + get_vip_facts_for_prompt(name)
             injected;  save_fact/save_conversation(speaker_id) now fire
  → next session, same name → same hash id → history recalled
```

## Confidence model (design principle, minimal code now)

Chat identity is tagged **claimed / low-confidence**. Voice + face (future) are the
**confirmers**: they will be able to override or merge a chat-claimed identity (link
`hash("jacob hoppenstedt")`'s learned facts into a voice-confirmed VIP id). This
build simply keeps the buckets clean and separate so that merge is possible later;
it implements no merge logic itself.

## IP / "discerning thing" — deferred (stubbed)

At a party everyone shares one WiFi (often one public IP), so IP barely
disambiguates two same-named guests. The stronger key is a per-browser id in
`localStorage`, which needs web-client work. So: ship the core now; `client_id`
param is present and unused, ready for a phase-2 that threads a browser id (or IP)
through from the WS layer for same-name disambiguation. Documented, not built.

## Error handling

- `resolve_chat_identity` wraps its `memory`/`vip_knowledge` calls defensively; on
  any failure it falls back to `(hash(name), name)` so a typed name never crashes
  the turn (worst case: a plain hash id, no VIP normalization).
- Empty/blank name → returns None-equivalent and the caller leaves `speaker_id`
  unset (current behavior; no regression).

## Testing

- `resolve_chat_identity("Jacob")` (non-VIP) → returns a stable int id + "Jacob";
  called twice → same id (hash stability).
- `resolve_chat_identity(<VIP alias>)` → returns the VIP's canonical name (mock
  `vip_knowledge.is_vip` to return a profile) and a stable id keyed on canonical.
- Existing person match → returns that person's id, not a new hash (mock
  `find_person_by_name`).
- Defensive fallback: `vip_knowledge.is_vip` raising → still returns `(hash, name)`.
- Wire-up A (integration-ish): the audio-less name-parse branch sets `speaker_id`
  (mock `resolve_chat_identity`); assert it's set and non-None.
- No regression: `find_person_by_name` still exact; `presence_enter` still links.

## Rollout / safety

- Additive + reuses existing memory. Voice/presence paths unchanged in behavior
  (B is a pure refactor to the shared helper). No schema change.
