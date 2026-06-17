# 🔀 Switching Characters (and Personalizing Each One)

How to change who the bot *is* — by hand, no wizard — and how to give each
character its own knowledge, memories, voice, and personality.

A "character" is just a folder under `characters/`. Whichever one `config.json`
points at is the active one. There are ~47 today (`mario`, `march7th`, `sonic`,
`rudi`, the 34 Honkai Star Rail cast, `goku`, etc.).

---

## Part 1 — Switch the active character

### The reliable way: config + restart

1. Open `config.json` (repo root).
2. Change the `character` field to any folder name in `characters/`:
   ```json
   {
     "character": "march7th",
     ...
   }
   ```
3. Restart: `start.bat` (Windows) / `./start.sh` (Mac/Linux).

That's the whole switch. On boot, the server loads that one folder and wires
**everything** from it — personality, voice clone, memory, games, pronunciation,
sprites. This path is fully wired and is what to use when you care about getting
it 100% right (e.g. before a party).

**Valid names** = any folder under `characters/` that has a `character.yaml`
inside and does **not** start with `_` (those are shared, e.g. `_shared`).

Default if the field is missing or invalid → `mario`.

### The easy way: the Control Panel (`/control`)

To press buttons instead of running commands, open the admin control panel:

```
http://localhost:8765/control       (local)
https://<your-tunnel-url>/control    (remote, over the Cloudflare tunnel)
```

Paste the **admin key** (`admin_api_key` from `config.json`) and press **Connect**.
The key is stored only in your browser and sent with every action — the page bakes
in no secrets, so the URL is useless to anyone without the key. (This is the *admin*
key, not the guest mirror PIN.)

Everything on the panel is gated by that key:

| Control | What it does | Applies |
|---|---|---|
| **🎭 Character** | Dropdown + *Switch now (live)* or *Switch & Restart* | live / full reload |
| **⚙️ Safe settings** | Idle chatter on/off, idle "use-the-AI" chance, idle min/max seconds | on restart |
| **🔊 Volume** | Slider 0–2× — sets the bot's speaker volume on the party machine | live |
| **🌙 Night phase** | Force WARM_UP / PARTY_MODE / UNHINGED / WIND_DOWN, or AUTO | live |
| **🔁 Restart** | Reboots the server (type `RESTART` to confirm) | ~30–60s down |

Notes:
- **Switch now vs Switch & Restart** — "now" changes voice + personality instantly;
  "& Restart" also fully reloads the new character's memory, VIPs, and lore (see the
  reload-vs-restart tables below).
- **Volume** is the connected display's playback gain (loudness) — a character's
  actual *voice* is still set in its folder.
- **Night phase** normally advances on its own by party time; forcing a phase
  overrides the clock until you set it back to AUTO.
- **Restart** only brings the server back if it was launched via `start_server.bat`
  (or `start.bat`), which run it in a supervised loop. Launched another way → it
  exits and stays down.

### The scripting way: admin endpoints (curl)

The panel buttons just call these endpoints — handy for scripts. The character
swap is mid-session, no restart:

```bash
# List available characters + see the current one:
curl -X POST http://localhost:8765/admin/switch_character \
  -H "Content-Type: application/json" \
  -d '{"api_key":"YOUR_ADMIN_KEY"}'

# Switch live to Sonic:
curl -X POST http://localhost:8765/admin/switch_character \
  -H "Content-Type: application/json" \
  -d '{"character":"sonic","api_key":"YOUR_ADMIN_KEY"}'
```

(`api_key` = `admin_api_key` from `config.json`. The client also pops a
`character_switched` notice so the on-screen window follows along.)

The switch is persisted back into `config.json`, so a later restart keeps the
new character.

**What hot-swap re-wires instantly (✅ correct live):**

| Reloaded live | Effect |
|---|---|
| System prompt + personality | New voice/attitude in replies |
| **Voice clone + Edge voice** | Speaks in the new character's voice *(fixed — used to keep the old voice)* |
| Pronunciation (global + char) | Right name pronunciations |
| Games + game pools | Character-specific game content |
| Command handlers + extras | Easter eggs, secrets, dares for the new char |
| Gossip / stats / emotions / night-progression / birthday modules | Renamed to the new character |

**What hot-swap does NOT reload — restart for these (⚠️):**

| Not reloaded live | Why it matters |
|---|---|
| Qdrant **memory** collection | The new char still queries the *previous* char's semantic memories |
| **VIP profiles** (`memories/vip_profiles/`) | New char's VIP dossiers aren't loaded until restart |
| **Lore** (`memories/hsr_lore.yaml`) | New char's world-lore facts aren't loaded until restart |
| Face / voice recognition collections | Guest face/voice matching stays on the old char's data |
| Sprites | The client keeps showing the old sprites until it reconnects/restarts |

**Rule of thumb:** hot-swap is great for a quick personality/voice change on the
fly (party gag, demo). For a character that depends on its own memory, VIPs, or
lore being correct, do a **config + restart** switch.

---

## Part 2 — Personalize a character with its own data & knowledge

Everything specific to a character lives **inside its folder** —
`characters/<name>/`. Edit these files, then **restart** (knowledge is
re-ingested into that character's vector memory on boot).

```
characters/<name>/
├── character.yaml              ← identity, voice, visuals, personality, memory wiring
├── prompts/
│   ├── system_prompt.md        ← core personality + behavior instructions
│   ├── greetings.yaml          ← event-triggered greeting lines
│   ├── phases.yaml             ← party-phase personality shifts
│   ├── guest_type_hints.yaml   ← per guest-type behavior
│   └── time_flavors.yaml       ← time-of-day / day-of-week flavor
├── memories/
│   ├── hsr_lore.yaml           ← world / character knowledge facts (→ Qdrant)
│   └── vip_profiles/<name>.json← dossiers on specific real people (→ Qdrant)
├── catchphrases/*.yaml         ← signature phrases
├── games/*.yaml                ← character-specific game content
├── idle/
│   ├── messages.yaml           ← idle mumbles / jokes / songs
│   └── loneliness.yaml         ← "nobody's here" lines
├── content/extras.yaml         ← easter eggs, secrets, dares
├── voice/reference_audio.wav   ← voice-clone reference clip
└── sprites/                    ← emotion/state images
```

### Where to put which kind of knowledge

**1. "Things this character KNOWS" (lore, backstory, world facts)**
→ `memories/hsr_lore.yaml` — a flat list of fact strings. On startup these are
embedded into the character's own Qdrant memory collection and surface
automatically via semantic search when relevant.
```yaml
facts:
  - "March 7th lost her memories and was found frozen in space."
  - "She carries a camera everywhere and loves preserving moments."
  - "Her ice powers come from her connection to the Preservation path."
```

**2. "Facts about a specific PERSON" (guests, the birthday VIP, friends)**
→ `memories/vip_profiles/<person>.json` — one JSON per person. Injected via
semantic search so the character recalls them naturally (not hardcoded replies).
See the VIP Profile Schema in `.claude/CLAUDE.md` for all fields.
```json
{
  "name": "Jacob Hoppenstedt",
  "titles": ["Birthday VIP"],
  "memories": ["Loves retro games", "Studied CS", "Throws the best parties"]
}
```
> Party-wide birthday facts (`birthday_person_name`, `birthday_person_facts`)
> live in **`config.json`**, not the character folder — they apply to whoever is
> active. Use a VIP profile for character-scoped people instead.

**3. "How this character TALKS and ACTS" (personality, voice, attitude)**
→ `prompts/system_prompt.md` (the main instructions) **plus** the
`personality:` block in `character.yaml`:
```yaml
personality:
  baseline_emotion: happy
  baseline_energy: 0.8
  warmth: 0.85                  # 0=cold .. 1=warm toward strangers
  warmth_growth_per_visit: 0.0  # thaws as a guest returns
  cold_until_familiar: false    # true = guarded until they're a regular
  traits: [bubbly, cheerful, curious]
  temperament: >
    You are upbeat and instantly friendly. You bounce with energy and treat
    everyone like a potential friend.
  temperament_cold: >           # used while cold_until_familiar and still guarded
    You're reserved and a little wary of people you don't know yet.
```

**4. "Say my name / these words right" (pronunciation)**
→ `voice.pronunciation` in `character.yaml`. These layer on top of the global
rules in `characters/_shared/global_rules.yaml` (character wins on conflict):
```yaml
voice:
  pronunciation:
    Seele: "Say-luh"
    Bronya: "Brawn-yah"
```

**5. Catchphrases, games, idle chatter, easter eggs**
→ `catchphrases/*.yaml`, `games/*.yaml`, `idle/messages.yaml`,
`content/extras.yaml`. All character-scoped; game pools also pull in shared
content unless `games.include_shared: false`.

### Memory isolation

Each character has its **own** vector-memory collections, named in
`character.yaml`:
```yaml
memory:
  collections:
    faces: march7th_faces
    voices: march7th_voices
    memories: march7th_memories
```
So conversations, learned facts, faces, and voices stay siloed per character —
March doesn't inherit Mario's memories of the party. (This is exactly why a
**live** hot-swap leaves memory on the old collection until you restart.)

### After editing — restart

Knowledge files (`hsr_lore.yaml`, `vip_profiles/`) are ingested into Qdrant on
startup, and the system prompt / personality are wired at load. So after any
content edit: **restart the server** to make it take effect.

---

## Quick reference

| I want to… | Do this |
|---|---|
| Manage the bot by clicking buttons (local or remote) | Open `/control`, paste the admin key |
| Switch character for the party (do it right) | Edit `config.json` `character` → restart — or `/control` → *Switch & Restart* |
| Switch character live as a gag/demo | `/control` → *Switch now*, or `POST /admin/switch_character` |
| Turn the bot's volume up/down remotely | `/control` → Volume slider |
| Force / unstick the party mood (night phase) | `/control` → Night phase (AUTO = back to automatic) |
| Reboot the server from my phone | `/control` → Restart (type `RESTART`) |
| Give a character world/backstory knowledge | `memories/hsr_lore.yaml` → restart |
| Make it remember a specific person | `memories/vip_profiles/<name>.json` → restart |
| Change how it talks/feels | `prompts/system_prompt.md` + `personality:` block → restart |
| Fix a mispronounced name | `voice.pronunciation` in `character.yaml` → restart |
| Change its voice | `voice/reference_audio.wav` + `voice:` block → restart |
