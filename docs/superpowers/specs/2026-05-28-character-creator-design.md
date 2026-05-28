# Character Creator Wizard — Design Specification

**Date:** 2026-05-28
**Status:** Draft
**Author:** AI-assisted design

## Overview

A browser-based, step-by-step wizard that enables non-technical users to create fully functional AI characters without writing any code. The wizard generates all required configuration files (`character.yaml`), directory structures, sprite images, voice training data, and system prompts — producing a character identical in quality to the existing Mario/Sonic/Rudi characters.

## Core Principles

1. **Zero coding required** — every setting exposed through the UI
2. **Known character intelligence** — typing "Goku" auto-fills description, personality, theme colors, voice search, and sprite prompts
3. **Hardware-aware** — models that won't run are grayed out with clear explanations
4. **Progressive complexity** — simple defaults, advanced options tucked behind toggles
5. **Everything editable** — auto-filled values are starting points, not locked

## Architecture

### Components

```
character_creator/
├── server.py              # Standalone FastAPI server (port 8766)
├── static/
│   ├── index.html          # Single-page app (vanilla JS, no build step)
│   ├── styles.css          # Dark theme matching the mockups
│   └── wizard.js           # Wizard logic, step management, API calls
├── known_characters.json   # Database of known characters (name → auto-fill data)
├── voice_finder.py         # YouTube voice clip search/download via yt-dlp
├── sprite_generator.py     # Wraps existing SubNP/DALL-E pipeline + rembg
└── requirements.txt        # Minimal deps (fastapi, uvicorn, yt-dlp, rembg)
```

### Integration Points

- **Hardware detection**: imports `server/hardware.py` for GPU/RAM/CPU detection
- **Image generation**: wraps `client/generate_character_poses.py` pipeline (SubNP API + rembg)
- **Voice training**: triggers existing GPT-SoVITS/Fish Speech training pipelines
- **Character output**: writes to `characters/<name>/` using same structure as Mario/Sonic/Rudi
- **Ollama models**: queries `http://localhost:11434/api/tags` for installed models

### Launch Flow

```
User double-clicks setup.bat
  → setup.bat checks if characters/ has any non-_shared subdirectories
  → If none: auto-opens http://localhost:8766 (character creator)
  → If exists: proceeds to normal server startup
  
User double-clicks create_character.bat (anytime)
  → Starts character creator server on port 8766
  → Opens browser to http://localhost:8766
```

## Wizard Steps

### Step 1: Identity
- **Character type toggle**: Known Character ⟨auto-fills⟩ vs Original Character ⟨blank slate⟩
- **Name** (text input): triggers known-character lookup
- **Display name** (text input): auto-filled as "{Name} AI {emoji}"
- **Tagline** (text input): auto-filled for known characters
- **Description** (textarea, editable): auto-filled for known characters
- **Theme colors** (4 color pickers): primary, secondary, accent, text — auto-detected for known characters

### Step 2: Personality (skippable for known characters)
- **System prompt** (large textarea): pre-filled template, fully editable
- **Accent/speech markers** (tag input): e.g., "Uses Italian-accented English"
- **Catchphrases** (list editor): add/remove catchphrases
- **Personality sliders** (optional advanced):
  - Warmth (cold ↔ warm)
  - Chaos (orderly ↔ chaotic)
  - Sarcasm (sincere ↔ sarcastic)
- Auto-filled for known characters with "Skip — use defaults" option

### Step 3: Voice
- **Voice engine priority display**: shows available engines (Fish Speech → GPT-SoVITS → Edge+RVC → Edge) with hardware compatibility indicators
- **Reference audio** (three paths):
  1. **Upload** — drag-and-drop .wav/.mp3/.ogg (5-30s clean speech)
  2. **Record** — browser-based microphone recording
  3. **Auto-find online** (known characters only) — searches YouTube via yt-dlp, shows results, user picks or auto-selects best
- **Edge TTS base voice picker**: grid of available voices with preview buttons
- **Voice tuning**: speed slider (-50% to +50%), pitch slider (-10Hz to +10Hz)
- **Pronunciation rules**: word → phonetic override list editor
- **Test voice button**: generates a sample line using current settings

### Step 4: Appearance
- **Two paths**:
  1. **AI Generate All Poses** (~15-20 min):
     - Visual description textarea (auto-filled for known characters)
     - Art style picker: 3D Figurine, Anime, Pixel Art, Realistic, Cartoon
     - Shows all ~37 sprites that will be generated: 25 unique emotion sprites + 12 state sprites (see Canonical Pose & State Matrix)
     - "Generate All" button — shows progress with live preview
  2. **Upload Your Own Images**:
     - Guided grid with two sections: **Emotions** (25 slots) and **States** (12 slots)
     - Each slot shows the emotion/state name, emoji hint, and drag-and-drop upload area
     - Minimum recommended: 5 core emotions (happy, sad, angry, neutral, thinking) + 3 core states (idle, talking, listening)
     - Missing sprites auto-fallback to nearest uploaded (see Fallback Rules in matrix section)
- **Auto background removal** toggle (uses rembg)
- Both paths can be combined (generate base, then replace specific ones)

### Step 5: Hardware & Models
- **Auto-detected hardware cards**: GPU VRAM, RAM, CPU cores, performance tier
- **Model selector**: list of available Ollama models with:
  - VRAM requirement shown
  - ✓ Compatible (green), ⚠ Slow/CPU offload needed (yellow), ✗ Incompatible (grayed out, locked)
  - "RECOMMENDED" badge on best compatible model
- **Single model default**: one model picker for both fast and quality
- **Advanced toggle**: "Split into Fast/Quality models" — reveals dual-model picker
- **Performance preview**: estimated response time, TTS workers, memory limit based on selections

### Step 6: Review & Create
- **Summary cards**: all chosen settings at a glance (identity, voice, appearance, model)
- **Character card preview**: how the character will look in the main app
- **"Create Character" button**: generates all files and starts training
  - Creates `characters/<name>/` directory structure
  - Writes `character.yaml`
  - Copies/generates sprites
  - Writes system prompt and related files
  - Starts voice training if reference audio provided
  - Shows progress bar with status messages
- **"Edit Later" link**: saves draft, can resume from any step

## Known Character Database

`known_characters.json` contains pre-filled data for popular characters:

```json
{
  "goku": {
    "display_name": "Goku AI 🐉",
    "tagline": "Kamehameha!",
    "description": "The legendary Saiyan warrior from Dragon Ball...",
    "accent_markers": ["Speaks with enthusiastic, energetic tone", ...],
    "catchphrases": ["Kamehameha!", "I'm Goku!", ...],
    "theme_colors": {"primary": "#FF6B00", "secondary": "#0066CC", ...},
    "voice_search_terms": ["Goku voice clips clean", "Goku quotes compilation"],
    "edge_voice": "en-US-ChristopherNeural",
    "visual_description": "Goku from Dragon Ball Z, muscular Saiyan warrior...",
    "art_style": "anime"
  },
  "spongebob": { ... },
  "darth_vader": { ... }
}
```

Ships with 20-30 popular characters. Users can add their own via JSON or the wizard just works without it for original characters.

## Technology Choices

- **Frontend**: Vanilla HTML/CSS/JS (no React/build step — keeps it simple to deploy)
- **Backend**: Standalone FastAPI server (separate from main server, port 8766)
- **Styling**: Dark theme, matching the mockup colors (dark navy background, colored accents)
- **No database**: all state lives in the wizard session (localStorage) until final creation

## Error Handling

- **No GPU detected**: Voice engines show "CPU only" mode, Edge TTS prioritized
- **No Ollama**: shows install instructions with link, still allows character creation
- **No yt-dlp**: auto-find voice clips disabled, upload/record still work
- **Image generation fails**: falls back to placeholder sprites, user can retry or upload
- **Partial creation**: if wizard interrupted, created files are valid (character works with defaults)

## Documentation Deliverables

- Updated `README.md` with "Getting Started" section for total beginners
- `docs/creating-a-character.md` — step-by-step beginner guide with screenshots
- `docs/character-format.md` — technical reference for power users who want to edit YAML directly
- Inline help text in every wizard step

## Canonical Pose & State Matrix

The wizard generates sprites for the following canonical emotion and state maps. These are derived directly from the existing Mario/Sonic/Rudi `character.yaml` files.

### Emotion Sprite Map (37 mapped entries → 25 unique sprites)

The emotion map has 37 total entries, but many are aliases pointing to the same sprite. The wizard generates **25 unique emotion sprites** (one per unique path).

| Emotion | Sprite Path | Category |
|---------|-------------|----------|
| happy | positive/happy | positive |
| excited | positive/excited | positive |
| laughing | positive/laughing | positive |
| love | positive/love | positive |
| loving | positive/love | positive |
| proud | positive/proud | positive |
| sad | negative/sad | negative |
| angry | negative/angry | negative |
| annoyed | negative/annoyed | negative |
| frustrated | negative/annoyed | negative |
| nervous | negative/nervous | negative |
| worried | negative/nervous | negative |
| scared | negative/scared | negative |
| embarrassed | negative/embarrassed | negative |
| disgusted | negative/disgusted | negative |
| grossed_out | negative/grossed_out | negative |
| confused | thinking/confused | thinking |
| thinking | thinking/thinking | thinking |
| curious | thinking/curious | thinking |
| determined | thinking/determined | thinking |
| mischievous | thinking/mischievous | thinking |
| shocked | thinking/shocked | thinking |
| idea | thinking/idea | thinking |
| surprised | thinking/surprised | thinking |
| mind_blown | reactions/mind_blown | reactions |
| sassy | reactions/sassy | reactions |
| cringe | reactions/cringe | reactions |
| impressed | reactions/impressed | reactions |
| sleepy | sleep/sleepy | sleep |
| bored | sleep/yawning | sleep |
| neutral | neutral/idle | neutral |
| memorial | memorial/moment_of_silence | memorial |
| solemn | memorial/moment_of_silence | memorial |
| toast | toast/raising_glass | toast |
| party | party/celebrate | party |
| celebratory | party/celebrate | party |
| birthday | birthday/birthday | birthday |

Note: Some emotions are aliases (e.g., loving → love, frustrated → annoyed). The wizard generates one sprite per unique path (~25 unique sprites) and maps aliases in `character.yaml`.

### State Sprite Map (9 states → sprite paths)

These are the 9 states used by all existing characters:

| State | Sprite Path(s) | Notes |
|-------|----------------|-------|
| idle | neutral/idle | Single sprite |
| talking | speech/talking, speech/talking_excited | Array: random selection at runtime |
| listening | speech/listening | Single sprite |
| greeting | greeting/wave | Single sprite |
| thinking | thinking/thinking | Single sprite |
| sleeping | sleep/sleeping | Single sprite |
| dancing | movement/dancing, party/celebrate | Array: random selection at runtime |
| entering | movement/entering | Single sprite |
| exiting | greeting/farewell | Single sprite |

### Sprite Generation Count

- **Unique emotion sprites to generate**: ~25 (after deduplicating aliases)
- **Unique state sprites to generate**: ~12 (including array variants like talking_excited)
- **Total unique sprites**: ~37 images
- **Generation time estimate**: ~15-20 minutes via SubNP API

### Fallback Rules

- Missing emotion sprites fall back to `neutral/idle`
- Missing state sprites fall back to `neutral/idle`
- If upload mode used with < 37 images, unmapped emotions resolve to the nearest category match (e.g., missing "proud" falls back to "happy")

## Voice Engine Selection & Fallback Rules

### Engine Priority and Required Artifacts

| Priority | Engine | Required Artifacts | VRAM Needed | Fallback Behavior |
|----------|--------|-------------------|-------------|-------------------|
| 1 | Fish Speech | `voice/reference_audio.wav` (5-30s clean speech) | ~4GB | Skip if no reference audio or package not installed |
| 2 | GPT-SoVITS | Trained model in `gpt_sovits_repo/` (global, shared across characters) + reference audio | ~8GB | Skip if not trained or unavailable |
| 3 | Edge TTS + RVC | `voice/rvc_model.pth` + Edge TTS base voice configured | ~2GB | Skip if no RVC model; fall through to Edge-only |
| 4 | Edge TTS (fallback) | Edge voice name in `character.yaml` (e.g., `en-US-GuyNeural`) | 0 (cloud) | Always available — ultimate fallback |

### Selection Rules

1. The `voice.preferred_engine` field in `character.yaml` is set to `"hybrid"` by default (tries all engines in priority order)
2. If user only uploads reference audio (no RVC training): Fish Speech is primary, Edge TTS is fallback
3. If user uploads reference audio AND trains RVC: Fish Speech → Edge+RVC → Edge
4. If user does full GPT-SoVITS training: Fish Speech → GPT-SoVITS → Edge+RVC → Edge
5. If user skips all voice training: Edge TTS only (preferred_engine set to `"edge"`)

### What the wizard writes to `character.yaml`

```yaml
voice:
  preferred_engine: "hybrid"  # or "edge" if no training done
  rvc_model: "voice/rvc_model.pth"  # omitted if not trained
  reference_audio: "voice/reference_audio.wav"  # omitted if not uploaded
  edge_voice: "en-US-ChristopherNeural"  # always set
  rate: "+15%"
  pitch: "+5Hz"
  pronunciation:
    kamehameha: "kah may hah may hah"
```

## Model Selection & Config Scope

### What the wizard controls

The wizard's model selection (Step 5) updates the **global** `config.json` file — specifically these fields:

```json
{
  "server": {
    "llm_quality_model": "gemma3:27b",
    "llm_fast_model": "llama3.1:8b"
  }
}
```

This is intentional: LLM models are a system-wide resource (loaded into GPU VRAM by Ollama), not per-character. The character defines personality/prompts; the model defines intelligence.

### Single vs Dual Model

- **Default (single)**: both `llm_quality_model` and `llm_fast_model` set to the same model
- **Advanced (dual)**: user explicitly picks two different models via the advanced toggle
- If `config.json` already has model values and user is creating a second character, the wizard shows current settings but does NOT overwrite unless the user explicitly changes them

### Hardware Gating Logic

```
if model.vram_required <= detected_vram:
    show as "✓ Compatible" (green, selectable)
elif model.vram_required <= detected_vram + (detected_ram * 0.3):
    show as "⚠ Slow — needs CPU offload" (yellow, selectable with warning)
else:
    show as "✗ Incompatible" (grayed out, not selectable)
```

## File Outputs

When the wizard completes, it creates:

```
characters/<name>/
├── character.yaml           # Full character config
├── sprites/                 # All sprite images (organized by emotion category)
│   ├── neutral/
│   ├── positive/
│   ├── negative/
│   ├── thinking/
│   ├── speech/
│   ├── greeting/
│   ├── reactions/
│   ├── sleep/
│   ├── movement/
│   ├── party/
│   ├── toast/
│   └── memorial/
├── catchphrases/            # YAML files with catchphrase pools
├── games/                   # Game pool overrides (if any)
├── prompts/
│   ├── system_prompt.md     # Main personality prompt
│   ├── idle_prompt.md       # What character does when alone
│   ├── greetings.yaml       # Event-triggered greeting templates
│   └── phases.yaml          # Party phase modifiers
├── idle/
│   ├── messages.yaml        # Idle chatter pools
│   └── loneliness.yaml      # What to say when lonely
├── memories/
│   └── vip_profiles/        # Empty, ready for runtime
├── voice/                   # Voice assets (if uploaded/trained)
│   ├── reference_audio.wav  # Reference clip for Fish Speech
│   └── rvc_model.pth        # RVC model (if trained)
└── test_phrases.yaml        # Test phrases for voice verification
```
