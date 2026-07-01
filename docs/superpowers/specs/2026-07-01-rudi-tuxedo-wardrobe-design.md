# Rudi Tuxedo Outfit + Wardrobe System — Design

**Date:** 2026-07-01
**Status:** Approved (design), in implementation
**Goal:** Give Rudi a black-tie tuxedo outfit for a friend's birthday party, and
build a minimal, reusable wardrobe system so a character can switch between
outfit sprite sets (config default now; live swap + a comedic "change real
quick" bit; auto-by-context left as a future hook).

## Motivation

Rudi's default look (oversized pink hoodie + navy denim shorts) reads as too
casual for a birthday party. He needs a formal outfit. The project has long
wanted per-character alternate outfit sprite sets (see
`characters/kafka/outfits/skirt/`, preserved for exactly this); this is the
first real implementation of that wardrobe idea.

## Scope

**In:**
- A tuxedo sprite set for Rudi at `characters/rudi/outfits/tuxedo/<category>/<pose>.png`.
- `character.yaml` gains an `visuals.outfits` map + optional `active_outfit`.
- Runtime outfit swap on the client (no restart) — reuses the existing
  character hot-swap machinery.
- `/outfit <name>` admin command + `outfit_switched` WS message.
- Config-driven startup outfit (`active_outfit`), so Rudi simply wears the tux
  at the party.
- A thin hook for the "gonna change real quick" gag (Rudi says a line, then the
  outfit swaps live).

**Out (YAGNI / future):**
- Auto-by-context outfit selection (party mode / birthday VIP → auto-formal).
  Leave a clearly-marked extension point only.
- Wardrobe picker UI, per-outfit voices, per-outfit personality.

## Image-Generation Track

The tuxedo sprites are derived mechanically from Rudi's existing hoodie prompts
so the character stays visually identical outfit-to-outfit — only the clothing
clause and the output path change.

- `scripts/_gen_rudi_tuxedo_prompts.py` reads `characters/rudi/sprite_prompts.txt`,
  swaps the one identical outfit clause (hoodie+shorts → black tuxedo) in all 39
  blocks, repoints `sprites/<p>` → `outfits/tuxedo/<p>`, front-loads the
  highest-traffic party poses (idle, talking, listening, greeting, party,
  birthday, smirk, hyped…), renumbers, and writes
  `characters/rudi/outfits/tuxedo/prompts.txt`. It asserts the hoodie clause is
  present in every block and that no old-outfit wording leaks into any body.
- `mcp_chatgpt/batch_sprites.py` gains `--prompts <relpath>`; the campaign
  manifest (`.regen_done.txt`) is derived next to the prompts file, so the
  outfit grind is isolated from the default set's manifest (default behavior
  unchanged).
- Generation: ChatGPT browser pipeline, all logged-in accounts, `--regen`,
  detached, resumable. Free-tier caps are hard (~1 img / 2–5 h / account), so
  the full 39-pose set fills in over days; priority ordering means a partial set
  still covers what guests actually see.

## Wardrobe Code Track

**Chosen approach: reuse the existing sprite hot-swap.** The client already
supports a full runtime character switch
(`client/main.py:_apply_character_switch`): update the `mario_display` module
globals (`AI_POSES_DIR`, `EMOTION_SPRITE_MAP`, `STATE_SPRITE_MAP`), clear
`display._sprites`, and call `display._load_sprites()`. An outfit swap is a
strict subset: same character, repoint `AI_POSES_DIR` at the outfit subtree and
reload. (Rejected: a cache-key-prefix scheme — more memory, invasive to
`_resolve_pose_key`; and a fake-character hack — pollutes the character list.)

### Components

1. **`shared/character_loader.py`** — parse `visuals.outfits` (name →
   `{dir, display, fallback}`) and `visuals.active_outfit`. Expose:
   - `outfits` (dict), `active_outfit` (str|None),
   - `outfit_poses_dir(name)` → absolute dir, `outfit_fallback(name)` → pose key.
   Unknown/blank outfit resolves to the default `sprites/` tree.

2. **`client/main.py`** — factor the swap guts of `_apply_character_switch` into
   a reusable `_apply_sprite_source(poses_dir, emotion_map, state_map, fallback)`.
   Add `_apply_outfit(name)` that repoints `AI_POSES_DIR` to the outfit dir and
   reloads. Apply `active_outfit` once at startup (after initial load).

3. **`client/mario_display.py`** — outfit-internal fallback: when the active
   source is an outfit and a requested pose key is absent, fall back to the
   **outfit's own fallback pose** (e.g. `neutral/idle` in the tux set), never to
   the default hoodie set. Keeps Rudi fully in-tuxedo while the set is partial.
   If the outfit dir is entirely missing/broken, fall back to the default
   character sprites (never crash to nothing).

4. **`client/ws_client.py`** — handle an `outfit_switched` message (mirrors
   `character_switched`) → callback into `MarioClient._apply_outfit`.

5. **`server/main.py` + `server/command_handlers.py`** — `/outfit <name>` admin
   command broadcasts `outfit_switched`. Read `active_outfit` from config at
   startup and push it to the client on connect. Provide a thin
   `trigger_outfit_change(name, line=None)` used by the gag: send Rudi's spoken
   line, then emit `outfit_switched` after a short beat.

6. **`config.json` / `config.example.json`** — `active_outfit` field. (config.json
   is gitignored; the template goes in config.example.json.) Default absent/empty
   = default outfit. Set `"tuxedo"` for the party.

### Data flow (outfit swap)

```
/outfit tuxedo  (admin)            gag: trigger_outfit_change("hold on…", "tuxedo")
        │                                    │  (speak line, beat)
        ▼                                    ▼
server broadcasts WS {type:"outfit_switched", outfit:"tuxedo"}
        ▼
client ws_client → MarioClient._apply_outfit("tuxedo")
        ▼
loader.outfit_poses_dir("tuxedo") → characters/rudi/outfits/tuxedo/
        ▼
AI_POSES_DIR repointed → display._sprites.clear() → display._load_sprites()
        ▼
missing tux pose → outfit fallback (tux idle), never the hoodie
```

## Error handling / edge cases

- Unknown outfit name → no-op (log + keep current), never crash.
- Empty/partial outfit dir → missing poses fall back to the outfit's fallback
  pose; a totally-empty dir falls back to the default character set.
- `active_outfit` naming a non-existent outfit → default set, logged.
- Outfit swap must be idempotent (swapping to the current outfit is a cheap
  no-op or a harmless reload).

## Testing

- Loader parses `visuals.outfits` + `active_outfit`; unknown outfit resolves to
  default; `outfit_poses_dir`/`outfit_fallback` correct.
- Outfit swap repoints the source and reloads the cache (globals updated,
  `_sprites` repopulated from the outfit dir).
- Missing pose in an outfit resolves to the outfit fallback, NOT the default
  set (the coherence guarantee).
- Unknown-outfit swap is a safe no-op.
- `batch_sprites` `--prompts` parses the outfit file and derives the isolated
  manifest path.

## Rollout

1. Land code + tests (default behavior unchanged when no outfit configured).
2. Let the sprite grind fill `outfits/tuxedo/` over days (resumable).
3. Set `active_outfit: tuxedo` in config.json for the party; use `/outfit
   default` / `/outfit tuxedo` and the gag hook live.
