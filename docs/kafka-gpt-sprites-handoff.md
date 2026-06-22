# Kafka — GPT Sprite Generation Handoff

**For:** an AI executing Kafka's sprite generation via ChatGPT (GPT image gen).
**Repo:** `C:\Users\Vketh\Desktop\Mario_AI`
**Goal:** regenerate Kafka's full sprite set with **ChatGPT (DALL·E via the browser tool)** — replacing her current flux sprites with GPT ones, exactly like Reze was done.

---

## Current state (as of 2026-06-22)
- Kafka has **37 sprites on disk**, all **Pollinations/flux** (listed in `.secrets/flux_drip_state.json`). **No `.regen_done.txt`** → none are GPT yet.
- Prompts exist at `characters/kafka/sprite_prompts.txt` **but in the wrong format** (manual copy-paste, not batch) — see Prerequisite below.
- Kafka = Honkai Star Rail (HoYoverse) — **copyrighted**. ChatGPT *did* draw Reze (Chainsaw Man) without refusing, so **try GPT first**; fall back only if it refuses.

## Who Kafka is (for verifying the output)
Stellaron Hunter from Honkai: Star Rail — adult woman, long wavy **purple/violet hair**, sharp violet eyes, elegant dark purple bodysuit with gold/teal accents and a long coat, confident sultry expression. Verify each sprite is actually her (purple hair, mature, not a generic anime girl).

---

## ⚠️ Prerequisite: reformat the prompt file (Kafka-specific)
The batch tool reads `[NN] sprites/<path>.png` blocks. Kafka's `sprite_prompts.txt` is manual-paste format. **Reformat it to match `characters/reze/sprite_prompts.txt`** (already in the right format — use it as the template):
```
[01] sprites/positive/happy.png
----------------------------------------------------------------------
<MASTER DESCRIPTION>  <pose for happy>, anime art style, cel-shaded, full body, plain background, full body in frame, nothing cropped, centered, generous margin
```
- Pull the MASTER DESCRIPTION + each `Pose:` line from the existing `kafka/sprite_prompts.txt`.
- One block per required pose. Required paths = the keys in `characters/kafka/character.yaml` `emotion_sprite_map` + `state_sprite_map` (same 37-39 set the other characters use).
- Keep every prompt **self-contained** (full character description in each — the model has no memory between images).

---

## ⚠️ NON-NEGOTIABLE survival rules (assets have been lost here)
1. **Commit after the batch finishes:** `git add characters/kafka/sprites/ characters/kafka/.regen_done.txt` then commit + push. **NEVER `git add -A`.** NEVER commit `server/data/qdrant_*/**/*.lock`.
2. **NEVER** `git checkout`/`git clean`/`git reset --hard` a path with uncommitted sprites. Commit first.
3. The flux originals are already committed in git history — safe to overwrite, recoverable.
4. Trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
5. Login privacy: personal account OK; **do NOT read the user's chat history**; if prompted to share data, click **"No thanks."**

---

## Tool: `mcp_chatgpt` browser batch (GPT-first)

**Login (per account, manual browser):**
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._login_oneshot chatgpt <account>
# Chrome opens -> log in -> close -> profile saved to mcp_chatgpt/profile/ (gitignored)
```
Existing logged-in accounts: `default` (often capped 24h), and spares `acct3`, `acct4`, `acct5`, `work`.

**Verify the session + image gen works** (login check needs an IMAGE probe, not just text):
```bash
mcp_chatgpt/venv/Scripts/python.exe -m mcp_chatgpt._probe_site chatgpt --gen
```

**Run the batch** (after reformatting the prompts):
```bash
mcp_chatgpt/venv/Scripts/python.exe mcp_chatgpt/batch_sprites.py \
  --character kafka --regen --accounts acct3,acct4,acct5,work --delay 25 --max-cap-waits 2
```
- Reads `characters/kafka/sprite_prompts.txt` (the reformatted one).
- Cuts background (rembg isnet-general-use + alpha matting) → writes `characters/kafka/sprites/<path>.png`, tracks `.regen_done.txt` (resumable).
- **Do NOT have the editor's MCP server running during a batch** (Chrome profile conflict).
- Rotates accounts on cap; gives up after `--max-cap-waits` all-capped waits (don't let it 24h-sleep — watch the log; kill if it hits `WAITALL ... sleeping <big>s`).
- **Refusal handling:** if ChatGPT replies refusing to draw Kafka (copyright), that's the fallback trigger → see below.

Key flags: `--character`, `--regen` (overwrite + resume), `--force` (ignore manifest), `--start N`, `--accounts a,b,c`, `--delay`, `--max-cap-waits`.

## Capacity reality
ChatGPT **free** accounts cap at ~5 images/day each. Kafka needs ~37 → you'll exhaust the spares. Options:
- Spread across all spares + finish over multiple days (caps reset 24h after hit), **or**
- If ChatGPT refuses Kafka OR you run out: fall back to **Gemini** (did Pomni's full 39 in one run):
  ```bash
  venv/Scripts/python.exe scripts/gen_sprites_from_prompts.py kafka --backend gemini --delay 5 --ref <kafka_reference.png>
  ```
  (`--ref` color-locks to a real Kafka image. Do NOT use `model=flux` on raw Pollinations URLs — HTTP 402.)

## Verify each sprite
- Transparent background, clean cutout (no halo / cut limbs).
- Full body in frame, centered, nothing cropped.
- **Actually Kafka** (purple hair, mature, HSR style) — not a generic.
- Re-roll bad ones.

## Commit when done
```bash
git add characters/kafka/sprites/ characters/kafka/.regen_done.txt
git commit -m "feat(kafka): GPT (ChatGPT) sprite set — regenerated from flux" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin master
```

## Reference
- General process + provenance details: `docs/weekend-image-gen-handoff.md`
- Working example (already done this way): Reze — `characters/reze/sprite_prompts.txt` (correct format) + `characters/reze/.regen_done.txt` (GPT manifest).
