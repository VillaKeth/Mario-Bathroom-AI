# Character Creator Wizard — Completeness Overhaul

**Date:** 2026-07-02
**Branch:** `feat/wizard-completeness` (worktree `.claude/worktrees/wizc`, base `ede0810`)
**Author:** audit-driven (5-agent parallel audit, 2026-07-02)

## Goal

Make a wizard-created character **100% ready for a non-programmer** — it can think, has sprites, has a voice, has memories + VIPs, reaches feature parity with hand-built characters (Mario/Rudi), and launches cross-platform. Close every gap the audit surfaced.

Design principle being enforced (from `.claude/CLAUDE.md`): *"When the wizard finishes, the character is 100% ready to run. No manual steps. Zero coding knowledge required."*

## Locked decisions (user, 2026-07-02)

- **ChatGPT sprites** = drive the chatgpt.com website via browser automation (`mcp_chatgpt/batch_sprites.py`). Wire that pipeline into the wizard UI with live progress + a guided one-time login. Keep the 7 API/local backends as keyless fallback.
- **Memories + VIP UI** = full VIP schema form + repeatable memory/fact rows.
- **Outfits** = build a minimal outfits UI now.
- **Delivery** = isolated worktree → branch → user review. No auto-merge to master (live concurrent session on the shared checkout).

## Baseline

300 targeted tests pass in the worktree. 1 pre-existing environmental failure (`test_vip_knowledge::test_inject_stores_in_qdrant`, Qdrant collection missing in a fresh worktree) — not in scope.

---

## Phase 1 — Silent-bug quick wins (mechanical, high ROI)

Content is generated but silently dropped by key-name mismatches between `content_generator.py` output and what the runtime reads.

| Bug | Fix | Files |
|-----|-----|-------|
| idle `trivia` → runtime reads `trivia_idle`; `hand_wash_reminders` → `handwash`; `fun_facts` orphan; `deep_thoughts` never generated | Align generator idle-pool keys to `idle_behavior.py:78-82`; add `deep_thoughts` spec; drop/rename `fun_facts` | `character_creator/content_generator.py`, cross-check `server/idle_behavior.py` |
| extras `encouragements` → handler reads `motivations`; 6 pools (`party_tricks`, `teasing`, `philosophical_questions`, `dad_jokes`, `puns`) have no consumer | Rename `encouragements`→`motivations`; wire or drop the 6 inert pools to match `command_handlers.py:58-76` | `character_creator/content_generator.py`, cross-check `server/command_handlers.py` |
| builder writes `memories/lore.yaml`; runtime reads `memories/hsr_lore.yaml` (`main.py:1151`) → lore never loads | Make loader read the builder's filename (or `lore_file` from `character.yaml`); write the filename the loader expects | `server/main.py`, `character_creator/character_builder.py` |

**Tests:** unit test that every generator pool key has a runtime consumer (guard against future drift); test lore file round-trips builder→loader.

## Phase 2 — No hollow shell

If content-gen is skipped or Ollama is down, the character has zero games and empty idle.

- `build_character()` seeds **minimal valid** `games/*.yaml` (a few items each) + a populated `idle/messages.yaml` so a character is never empty even pre-content-gen. (`character_builder.py:44,65`)
- Sprite **fresh-clone backend probe**: on the Appearance step, probe `detect_backends()`; if none usable, block generation with a clear "add a free HuggingFace token here" prompt instead of silently churning to "incomplete." (`sprite_generator.py:746`, `server.py` sprites status, `sprites.js`)
- **rembg cutout validation**: corner-alpha check; a sprite whose background wasn't removed must not count as "done" (currently raw-bytes fallback passes). (`sprite_generator.py:217-250`)

**Tests:** created character has non-empty games + idle before content-gen; probe returns "blocked" with zero backends; cutout validator rejects opaque-corner images.

## Phase 3 — Can-think

The selected LLM is never downloaded → finished character silently can't respond.

- Add `POST /api/models/pull` that runs `ollama pull <model>` and streams progress (SSE like content-gen). Trigger on model-select or at "Start Server". (`server.py` models section)
- Make "Recommended" **install-aware**: prefer an already-pulled compatible model. (`server.py:90-93`)
- In-flow Ollama **install/serve helper**: detect missing Ollama / dead `ollama serve` and surface one-click guidance rather than a terminal instruction. (`wizard.js:398`, `setup.bat:23,32`)

**Tests:** pull endpoint invokes `ollama pull` with the selected model; recommended-model picker prefers installed; graceful message when Ollama absent.

## Phase 4 — Cross-platform + robustness

- `/api/server/launch`: pick `start.sh` on non-Windows, `start.bat` on Windows. (`server.py:115-131`)
- **Name collision**: on "directory already exists," offer Overwrite / Rename in the UI instead of a no-op retry loop. (`character_builder.py:40`, `wizard.js:2059`)
- Write `config.json` `character` at **create time**, not only on the success screen — closing the tab after "Create Character" must still leave the character active. (`wizard.js:2308` → move into create flow)

**Tests:** launch chooses correct script per platform; collision returns a structured choice; create writes active character.

## Phase 5 — Memories + VIPs (new feature)

No UI or endpoints exist for the runtime VIP/memory system today.

- **Endpoints:** `POST/GET/DELETE /api/vip/{char}` (read/write `characters/<char>/memories/vip_profiles/<slug>.json`); `POST/GET /api/memories/{char}` (append/list `memories/lore.yaml` `facts[]`).
- **Wizard step "Guests & Memories":** full VIP schema form (name, aliases, hometown, age, birthday, education, titles, family, projects, skills, personality_notes, mario_conversation_hooks, memorial, memories[]) + repeatable fact rows.
- Extend `create-character` payload + `build_character` to accept `vips: [...]` and `facts: [...]` and write them during creation.
- Upgrade the lone `event-vip` name box into a light VIP profile (name + birthday + a couple facts).
- Runtime already consumes `characters/<char>/memories/vip_profiles/` (`main.py:1142`, `vip_knowledge.py:24`) — profiles work the instant written; no runtime change beyond the Phase 1 lore-filename fix.

**Tests:** VIP CRUD round-trips schema-valid JSON to the right dir; memories endpoint appends to `facts[]`; create-character with `vips`/`facts` populates files; a created character's VIP dir is loadable by `load_all_vip_profiles()`.

## Phase 6 — Parity toggles

- **Safety / uncensored toggle:** wizard writes a `safety:` block (`enabled`, `block_slurs`) so a user can make an uncensored character. Loader currently defaults to censored when absent. (`character_builder.py`, `character_loader.py:145`, ref `rudi.yaml:125`)
- **Minimal outfits UI:** an "Outfits" affordance to add a named outfit and generate/upload its sprite set into `characters/<char>/outfits/<name>/`, writing `visuals.outfits` in `character.yaml`. Reuses the existing sprite pipeline + the wardrobe schema already shipped for Rudi (ref `rudi.yaml:99`, `/outfit` runtime swap).

**Tests:** safety block written and honored by loader; outfit dir + `visuals.outfits` entry created; outfit sprite set generates via existing pipeline.

## Phase 7 — ChatGPT sprites wired into the UI

- Add a **`chatgpt` sprite backend** that shells `mcp_chatgpt/batch_sprites.py` via subprocess (mirroring the `start.bat` Popen at `server.py:123`) and streams its stdout into `_generation_tasks` progress.
- **Guided one-time login**: a UI step that runs `python -m mcp_chatgpt._login_oneshot chatgpt <account>` and confirms session validity before batch generation. (Login cannot be fully eliminated — chatgpt.com requires it — but everything around it becomes clicks.)
- Handle the "MCP server must be closed / profile in use" conflict with a clear message. (`batch_sprites.py:11-13,93`)
- Honest labeling: relabel the paid "OpenAI" API card so it isn't confused with free browser ChatGPT.

**Tests:** backend registered + selectable; subprocess wiring invoked with the character's `sprite_prompts.txt`; login-required and profile-in-use states surface structured errors (mock the browser layer — no live login in CI).

## Phase 8 — Tests + live verify

- Full targeted suite green (the 300 baseline + all new tests).
- Live smoke per `.claude/rules/testing.md`: create a throwaway character end-to-end; confirm it launches, responds (can-think), speaks (audio `_play_wav: playing`/`done`), and shows no wrong-character leaks.

---

## Testing strategy

TDD per change: write/adjust the failing test, implement, confirm green, never regress the 300 baseline. New cross-cutting guard: a test asserting **every generated content-pool key maps to a runtime consumer** (prevents Phase 1 class of bug recurring).

## Risks / constraints

- **Concurrent session** on the shared checkout — all work stays in this worktree; no merge to master without user review.
- **Windows long paths** — `core.longpaths=true` set (required for worktree checkout of `mario_3d_assets/`).
- **Heavy deps** — GPT-SoVITS / torch / browser automation not exercised in CI; those paths are unit-tested with mocks, verified live in Phase 8.
- **ChatGPT login** — irreducible one-time manual step; scope is to minimize surrounding friction, not eliminate login.

## Delivery

Sequential phases 1→8, each committed separately with tests. On completion: present the branch + a summary for user review. User decides merge to master.
