# Weekend Image-Gen Handoff

**For:** the AI running sprite generation over the weekend (Sat 2026-06-20 → Sun 2026-06-21).
**Repo:** `C:\Users\Vketh\Desktop\Mario_AI`
**Goal:** keep image generation running continuously — **at least one batch active per day**. When a character's set finishes, move to the next; when all targets are done, do quality-refresh re-rolls or start the next HSR character.

---

## Prime directive: GPT-first, fall back on refusal

For **every** character, **try ChatGPT first** (via the `mcp_chatgpt` browser tool). ChatGPT (DALL·E) often *will* draw well-known characters — Mario (Nintendo) was generated entirely through it. So do not pre-assume a refusal.

- **If ChatGPT produces the image → use it** (preferred, best quality + consistency).
- **If ChatGPT REFUSES** (replies with a "can't create that"/policy message instead of an image) → that character is copyright-blocked on GPT → **fall back to the non-GPT backend** (HuggingFace FLUX → Pollinations flux). Keep whatever already exists.

Copyright status of the targets: Mario = Nintendo, Kafka = Honkai Star Rail (HoYoverse), Reze = Chainsaw Man (MAPPA/Fujimoto). All three are IP characters — try GPT, fall back if blocked.

---

## ⚠️ NON-NEGOTIABLE survival rules (assets have been lost here before)

1. **Commit generated sprites after each character finishes.** `git add characters/<char>/sprites/<specific paths>` then commit + push. **NEVER `git add -A`.** **NEVER** commit `server/data/qdrant_*/**/*.lock`.
2. **NEVER** run `git checkout <path>`, `git clean`, or `git reset --hard` on a path holding uncommitted generated sprites — that is exactly how a previous set got wiped. Commit first, always.
3. Uncommitted sprites are one bad command from gone. Commit early, commit often, push to origin.
4. Commit trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
5. Account/login privacy (user's rules): logging in on a **personal** account is fine; **do NOT read the user's chat history**; if a site prompts to share data, click **"No thanks."**

---

## Current state (as of Fri 2026-06-19)

| Char | Sprites | Provenance | Weekend action |
|------|---------|------------|----------------|
| **mario** | 42 / 43 — missing `sprites/bathroom/grossed_out.png` | **GPT** (`characters/mario/.regen_done.txt`) | Generate the 1 missing pose via GPT. Optional GPT quality refresh of any weak ones. |
| **kafka** | complete per its `character.yaml` map | unclear (no `.regen_done.txt`) | Full **GPT** refresh for consistency; fall back to flux if HSR is refused. Fill any gaps vs the 39-pose standard. |
| **reze** | 39 / 39 | **ALL Pollinations/flux** — every pose is in `.secrets/flux_drip_state.json`; there is **no `.regen_done.txt`**, so per the records **none are GPT** (despite a hunch that "a few already are"). | **Regenerate all 39 via GPT** (user's explicit ask). Fall back to flux `--ref` if Chainsaw Man is refused. |

### How to tell GPT vs non-GPT provenance
- `characters/<char>/.regen_done.txt` exists → that char was **GPT**-generated (mcp_chatgpt writes it).
- `.secrets/flux_drip_state.json` `"done"` array lists `<char>/<pose>` → **Pollinations flux**.
- Tracked at **character-batch level**, not per-sprite. A successful GPT batch writes/updates `.regen_done.txt` — so after converting Reze, commit the new `.regen_done.txt` too (that's the record that she's now GPT).

---

## Tool A — GPT (preferred): `mcp_chatgpt` browser batch

**One-time login per account** (no terminal input; manual browser):
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot chatgpt <account>
# Chrome opens -> log in manually -> close window -> profile saved to mcp_chatgpt/profiles/ (gitignored)
```

**Verify the session + that image gen actually works** (the login check needs an **image** probe, not just text):
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._probe_site chatgpt --gen
```

**Run a batch:**
```bash
mcp_chatgpt/venv/Scripts/python.exe mcp_chatgpt/batch_sprites.py \
  --character <char> --regen --accounts <a,b> --delay 30 --max-cap-waits 8
```
- Reads `characters/<char>/sprite_prompts.txt`. **mario** is already in batch format (`[NN] sprites/<path>.png` + `----` + prompt). **kafka** and **reze** prompt files are in paste/markdown format — **reformat them to the `[NN] sprites/<path>.png` block format first** (match mario's file).
- Cuts background (rembg `isnet-general-use` + alpha matting), writes `characters/<char>/sprites/<path>.png`, tracks `.regen_done.txt` (resumable).
- **Do NOT have the editor's MCP server running during a batch** — Chrome profile conflict.
- Rate limits: it self-waits on the page's reset timer and rotates accounts; gives up after `--max-cap-waits` all-capped waits.
- **Refusal = fall back to Tool B** for that character.

Key flags: `--character`, `--regen` (overwrite + resume), `--force` (ignore manifest), `--start N`, `--accounts a,b`, `--delay`, `--cap-fallback` (sec), `--max-cap-waits`.

---

## Tool B — non-GPT fallback: `scripts/gen_sprites_from_prompts.py`

```bash
venv/Scripts/python.exe scripts/gen_sprites_from_prompts.py <char> \
  --backend huggingface --delay 5 --ref <reference_image.png>
```
- Backends in order: **huggingface** (FLUX.1-dev, free monthly credits) → **pollinations** flux (budget-gated via `.secrets/`) → grok/openai/gemini (paid, only if keys + budget set in `character_creator/sprite_config.json`).
- `--ref <path>` color-locks via Gemini multimodal — **use a canonical reference image** of the character for faithful colors.
- `--force` re-rolls existing; default skips existing (resumable). Reads the same `sprite_prompts.txt`.
- **Do NOT pass `model=flux` on raw Pollinations URLs — it returns HTTP 402.** Use the script's backends (they handle this).
- Economics: free Pollinations *sana* is usually queue-blocked; paid *flux* ≈ 0.00175/img, budget-capped. Check `.secrets/pollinations_spend.json` + the budget in `sprite_config.json` before large paid runs.

---

## Suggested cadence (keep something always running)

- **Sat AM — Reze (biggest job):** reformat `characters/reze/sprite_prompts.txt` to batch format, run GPT batch for all 39. If Chainsaw Man is refused, fall back to `gen_sprites_from_prompts.py reze --ref` to refresh quality. Commit + push when done.
- **Sat PM — Mario:** generate the missing `bathroom/grossed_out`, then optional GPT refresh of weak poses. Commit + push.
- **Sun AM — Kafka:** GPT refresh / fill gaps; fall back to flux if HSR is refused. Commit + push.
- **Sun PM — Quality pass:** re-roll any sprite that came out cropped, wrong-color, or with a bad cutout (halo/cut edges). Commit + push.
- **If everything's done early:** start the next HSR character — see `batch_generate_hsr.py --status` and `setup_hsr_characters.py` for the 34-char list; generate its set (GPT-first, flux fallback).

---

## Verify each sprite before accepting (per `.claude/rules/`)

- Transparent background, clean cutout (no halo, no cut-off limbs).
- Full body in frame, centered, nothing cropped at edges.
- Correct character + correct colors (for IP characters, confirm it's actually them, not a generic stand-in).
- Re-roll anything that fails; don't ship bad sprites.

---

## Commit cadence (do this per character)
```bash
git add characters/<char>/sprites/ characters/<char>/.regen_done.txt
git commit -m "feat(<char>): <GPT|flux> sprite batch — <what changed>" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin <branch>
```
Work on a branch if master is being actively changed by another process; otherwise commit to `master`. Confirm `git status` shows only intended files before every `add`.
