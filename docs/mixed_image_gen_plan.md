# Mixed Image Generation — Design Plan

Goal: higher-quality sprites/backgrounds by routing across **multiple image
providers** (Grok / xAI, Google Gemini-Imagen, OpenAI gpt-image-1, plus the
existing HuggingFace / A1111 / ComfyUI / Pollinations), each with **one
official key**, falling back when a provider is rate-limited or down.

This is the clean, ToS-safe version of "use better free models." It does NOT
rotate throwaway accounts to dodge quotas (against every provider's ToS, gets
keys/IPs banned mid-party). One key per provider; round-robin **across
providers**, not duplicate accounts.

---

## 1. Why

Current backends (sana/flux-schnell via Pollinations, SD1.5 local) frame and
render worse than the frontier image models. Grok, gpt-image-1, and Imagen 3
produce cleaner full-body characters with correct anatomy and framing — fewer
redo cycles, better party visuals.

## 2. Architecture (fits the existing pattern)

`character_creator/sprite_generator.py` already has a backend cascade:
`generate_single_pose()` builds `order = [...]` and tries each
`_generate_<backend>()` in turn. The plan extends this, no rewrite.

### 2a. New backend functions
Each mirrors the existing `async def _generate_<x>(prompt, ...) -> bytes | None`
contract (return PNG/JPEG bytes or None; never raise):

- `_generate_grok(prompt, key)` — xAI `POST https://api.x.ai/v1/images/generations`,
  model `grok-2-image` (or current). Bearer key. Returns URL → fetch bytes.
- `_generate_openai_image(prompt, key)` — `POST /v1/images/generations`,
  model `gpt-image-1`, `size=1024x1536` (portrait), `quality=medium`.
  Returns b64 → bytes.
- `_generate_gemini_image(prompt, key)` — Google GenAI `:generateContent` with
  an image-out model (Imagen 3 / `gemini-2.x-image`). Returns inline b64 bytes.

All three accept the same `FRAMING_SUFFIX` already appended upstream — no
per-backend prompt logic.

### 2b. Provider registry + router
Replace the hardcoded `order` list with a **provider registry**:

```
PROVIDERS = {
  "grok":        {"fn": _generate_grok,        "key": cfg["grok_key"],   "quality": 9},
  "openai":      {"fn": _generate_openai_image,"key": cfg["openai_key"], "quality": 9},
  "gemini":      {"fn": _generate_gemini_image,"key": cfg["gemini_key"], "quality": 8},
  "huggingface": {"fn": _generate_huggingface, "key": cfg["hf_token"],   "quality": 7},
  "pollinations":{"fn": _generate_pollinations,"key": None,              "quality": 5},
  "a1111":       {"fn": _generate_a1111,       "key": None,              "quality": 6},
}
```

Router policy (config-selectable):
- **`quality`** (default): try highest-quality available provider first, fall
  through on failure/rate-limit.
- **`round_robin`**: rotate across providers with a key set, to spread load and
  stay under each provider's rate limit. A per-provider cooldown timestamp
  (in-memory) skips one that just returned 429 until its window resets.
- **`cheapest`**: free/local first (current behavior), paid last.

429 / quota errors mark `cooldown_until = now + retry_after` and move on — this
is the legitimate "don't hammer one provider" behavior, distinct from account
rotation.

### 2c. Cost ledger (extend existing)
Pollinations already has `.secrets/pollinations_spend.json`. Generalize to
`.secrets/image_spend.json` keyed by provider with per-provider budgets in
`sprite_config.json` (e.g. `{"openai_budget": 5.0, "grok_budget": 5.0}`).
gpt-image-1 ≈ $0.04/medium image, Grok ≈ $0.07, Imagen ≈ $0.04 — so a 39-sprite
character is ~$1.5–2.7. Budget cap + ledger prevents surprise spend, same
guardrail as the pollen drip.

## 3. Config + Wizard UI

`sprite_config.json` gains: `grok_key`, `openai_key`, `gemini_key`,
`*_budget`, `router_policy`. The Sprite Manager **⚙️ Image AI Settings** panel
already exists — add:
- key inputs (password-masked, same pattern as `hf_token`),
- a router-policy dropdown (quality / round-robin / cheapest),
- per-provider budget fields,
- live availability badges (probe each key with a cheap models-list call).

Keys live in `sprite_config.json` (gitignored like the pollinations token) or
env (`OPENAI_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY`).

## 4. Security / ToS guardrails (hard rules)

- **One key per provider.** No multi-account rotation, no quota evasion. The
  router rotates across *different providers*, never across duplicate accounts
  of the same provider.
- Keys gitignored, never logged, masked in API responses (mirror the existing
  `hf_token` masking in `/api/sprites/config`).
- Per-provider budget cap + ledger; default budgets 0 (off) so nothing spends
  until the user opts in with a key + budget.
- Respect 429 `Retry-After`; exponential backoff; never retry-storm.

## 5. Rollout

1. Add the three backend fns + provider registry + router policy (no UI yet);
   default policy `cheapest` so behavior is unchanged until keys added.
2. Generalize the spend ledger to multi-provider.
3. Wizard settings UI: keys, policy, budgets, availability badges.
4. A/B harness (`scripts/ab_sprite_test.py` already exists) → render the same
   pose through every configured provider, pick the best looking, set it as the
   character's default backend.
5. Optional: a `quality_backend` per character in `character.yaml` so a
   character can pin its best-looking provider.

## 6. Effort

- Backends + router + ledger: ~half a day, low risk (isolated, additive).
- Wizard UI: ~2–3 hours (the settings panel scaffold exists).
- Testing: A/B one character end-to-end per provider.

No changes to the party server or client — sprites are produced offline by the
wizard/drip; the runtime just loads PNGs.
