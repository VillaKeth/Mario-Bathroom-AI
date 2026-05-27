# Modular Character System — Design Spec

**Date:** 2026-05-25
**Status:** Draft (pending user approval)
**Safety Net:** Tag `v1.0-mario-stable` at commit `d28ba62`

## Problem

The Mario AI party bot has all character identity hardcoded throughout the codebase — system prompt embedded in `server/main.py`, sprite paths in `client/mario_display.py`, voice model references in `server/tts.py`, game pools in `server/game_handlers.py`. Switching to a different character (Sonic, Rudi, etc.) requires modifying dozens of files.

## Solution

A modular character system where each character is a self-contained directory with a YAML config, and a `CharacterLoader` class wires everything up at startup.

## Architecture

### Character Directory Structure

```
characters/
  _shared/                        # Global content for ALL characters
    events/
      party_events.yaml
      shot_events.json
    games/
      would_you_rather.yaml
      never_have_i_ever.yaml
      truth_or_dare.yaml
      riddles.yaml
      rapid_fire.yaml
  mario/                           # Character-specific package
    character.yaml                 # Config (identity, voice, visuals, games, memory)
    prompts/                       # AI persona prompts
      system_prompt.md             # Core persona (always injected)
      idle_prompt.md               # Idle monologue prompt
      phases.yaml                  # Party phase modifiers (WARM_UP, PARTY_MODE, etc.)
      greetings.yaml               # Event prompts (enter_known, exit_unknown, etc.)
      guest_type_hints.yaml        # Guest personality adaptation hints
      time_flavors.yaml            # Time-of-day flavor text
    sprites/                       # Emotion-mapped images
      idle.png
      talking.png
      happy.png, sad.png, angry.png, excited.png...
    voice/                         # Voice models
      rvc_model.pth                # Trained RVC voice conversion model
      reference_audio.wav          # Fish Speech / GPT-SoVITS reference sample
    catchphrases/                  # Pre-recorded WAV clips
      wahoo.wav, lets_go.wav, mama_mia.wav...
    games/                         # Character-specific game pools
      trivia.yaml                  # Mario-themed trivia questions
      reactions.yaml               # Win/lose/tie reaction text
      word_chains.yaml             # Starter words for word chain game
    memories/                      # Character knowledge
      vip_profiles/                # Known guest JSON files
        jacob_hoppenstedt.json
      lore.yaml                    # Character-specific knowledge base
```

### character.yaml Schema

```yaml
identity:
  name: "Mario"
  display_name: "Mario AI 🍄"
  tagline: "It's-a me!"
  description: "The famous plumber from the Mushroom Kingdom"

voice:
  preferred_engine: "hybrid"             # hybrid | sovits | edge | xtts
  rvc_model: "voice/rvc_model.pth"      # relative to character dir
  reference_audio: "voice/reference_audio.wav"
  edge_voice: "en-US-ChristopherNeural"
  rate: "+10%"
  pitch: "+5Hz"
  pronunciation:                        # word → phonetic substitutions
    "wahoo": "wah-hoo"
    "whoa": "woah"
    "yippee": "yip-pee"
    "mamma mia": "mama mee-ah"
    "mama mia": "mama mee-ah"
    "okie dokie": "oh-key doh-key"
    "ha ha ha": "hah hah hah"
    "ha ha": "hah hah"

visuals:
  sprite_dir: "sprites/"
  ai_poses_dir: "sprites/ai_poses/"       # AI-generated 3D pose PNGs
  ai_pose_size: [250, 250]                # display size for AI poses
  emotion_sprite_map:                     # emotion → AI pose category/filename
    happy: "positive/happy"
    excited: "positive/excited_jump"
    surprised: "thinking/surprised"
    confused: "thinking/confused"
    annoyed: "negative/annoyed"
    sleepy: "sleep/sleepy"
    mischievous: "thinking/mischievous"
    laughing: "positive/laughing"
    sad: "negative/sad"
    angry: "negative/angry"
    nervous: "negative/nervous"
    scared: "negative/scared"
    love: "positive/love"
    loving: "positive/love"
    proud: "positive/proud"
    embarrassed: "negative/embarrassed"
    disgusted: "negative/disgusted"
    determined: "thinking/determined"
    bored: "sleep/yawning"
    worried: "negative/nervous"
    curious: "thinking/curious"
    thinking: "thinking/thinking"
    shocked: "thinking/shocked"
    neutral: "neutral/idle"
    memorial: "memorial/moment_of_silence"
    toast: "toast/raising_glass"
    party: "party/celebrate"
    birthday: "birthday/birthday_boy"
    grossed_out: "bathroom/grossed_out"
    mind_blown: "reactions/mind_blown"
    sassy: "reactions/sassy"
    cringe: "reactions/cringe"
    impressed: "reactions/impressed"
    celebratory: "party/cheers"
    solemn: "memorial/moment_of_silence"
    idea: "thinking/idea"
    frustrated: "negative/annoyed"
  state_sprite_map:                       # state → AI pose (string or list for random)
    idle: "neutral/idle"
    talking: ["speech/talking", "speech/talking_excited"]
    listening: "speech/listening"
    greeting: "greeting/wave_high"
    thinking: "thinking/thinking"
    sleeping: "sleep/sleeping"
    dancing: ["movement/dancing_1", "movement/dancing_2", "party/celebrate"]
    entering: "movement/running"
    exiting: "greeting/farewell"
  fallback_sprites:                       # legacy 2D sprites (if AI poses missing)
    idle: "mario_idle.png"
    talking: "mario_talking.png"
  theme_colors:
    primary: "#E52521"
    secondary: "#049CD8"
    accent: "#FBD000"
    text: "#FFFFFF"
  particle_colors:
    - "#FFD700"
    - "#E52521"
    - "#049CD8"

speech:
  accent_markers:
    - "Uses Italian-accented English"
    - "Adds '-a' to words: 'it's-a me', 'let's-a go'"
    - "Catchphrases: Wahoo!, Mama mia!, Okie dokie!"
  catchphrase_dir: "catchphrases/"

games:
  pools_dir: "games/"
  include_shared: true

memory:
  collections:                            # explicit Qdrant collection names
    faces: "mario_faces"                  # face_memory.py (128-dim face encodings)
    voices: "mario_voices"                # speaker_id.py (256-dim voice embeddings)
    memories: "mario_memories"            # memory_semantic.py (384-dim text embeddings)
  vip_profiles_dir: "memories/vip_profiles/"
  lore_file: "memories/lore.yaml"
```

### Prompt System (Multi-File)

The current prompt model is more complex than a single file. `mario_prompt.py` contains:
- `MARIO_SYSTEM_PROMPT` — core persona (always injected)
- `PHASE_PROMPTS` — party phase modifiers (WARM_UP, PARTY_MODE, UNHINGED, WIND_DOWN)
- `GREETING_PROMPTS` — 15+ event-specific prompts (enter_known, exit_unknown, idle, etc.)
- `build_context()` — assembles full prompt from speaker, memories, events, phase
- `_LLM_IDLE_SYSTEM_PROMPT` — separate idle monologue prompt (in main.py)
- Helper functions: `_infer_guest_type`, `get_energy_hint`, `maybe_inject_catchphrase`, etc.

The character directory needs to support all of these:

```
characters/mario/
  prompts/
    system_prompt.md        # Core persona (replaces MARIO_SYSTEM_PROMPT)
    idle_prompt.md          # Idle monologue prompt (replaces _LLM_IDLE_SYSTEM_PROMPT)
    phases.yaml             # Phase modifiers (replaces PHASE_PROMPTS dict)
    greetings.yaml          # Event prompts (replaces GREETING_PROMPTS dict)
    guest_type_hints.yaml   # Guest personality hints (replaces GUEST_TYPE_HINTS)
    time_flavors.yaml       # Time-of-day flavor text
```

All `.md` files use `{{variable}}` substitution. Variables sourced from:
- `character.yaml` fields (static): `{{character_name}}`, `{{description}}`, `{{accent_markers}}`
- Runtime state (dynamic): `{{guest_name}}`, `{{party_context}}`, `{{visit_count}}`, `{{last_topic}}`
- Greeting-specific: `{{name}}`, `{{minutes}}`, `{{count}}`

The `build_context()` function moves into `CharacterLoader` and assembles the full prompt from these files + runtime state. The assembly process mirrors current `mario_prompt.build_context()`:

1. Start with `system_prompt.md` (core persona)
2. Inject `phases.yaml` modifier based on current party phase
3. Add `time_flavors.yaml` text for current time-of-day and day-of-week
4. Add `guest_type_hints.yaml` based on inferred guest personality
5. Inject VIP context if speaker matches a VIP profile
6. Add last emotion context for response continuity
7. If event-triggered, use `greetings.yaml` template with `{{name}}`, `{{visit_count}}`, `{{last_topic}}`
8. Inject conversation memories and guest_context
9. Sanitize final prompt (strip unsafe content)

Helper functions (`_infer_guest_type`, `get_energy_hint`, `maybe_inject_catchphrase`, `maybe_add_question`, `check_opener_variety`, etc.) remain in shared code since they are character-agnostic behavioral logic, not character identity.

### CharacterLoader Class

Single class in `shared/character_loader.py` (a new `shared/` package at project root), imported by both server and client via `from shared.character_loader import CharacterLoader`. Both `server/` and `client/` add the project root to `sys.path` (which they already do for cross-imports).

```python
class CharacterLoader:
    def __init__(self, characters_dir: str, character_name: str):
        # Reads characters/{name}/character.yaml
        # Validates required fields exist
        # Resolves all relative paths to absolute
        # Raises CharacterNotFoundError / CharacterConfigError on failure

    # Identity
    name: str
    display_name: str
    tagline: str
    character_dir: Path

    # Prompt System
    def get_system_prompt(self, context: dict) -> str:
        # Reads prompts/system_prompt.md, substitutes {{variables}}
    def get_idle_prompt(self) -> str:
        # Reads prompts/idle_prompt.md
    def get_phase_prompts(self) -> dict[str, str]:
        # Reads prompts/phases.yaml
    def get_greeting_prompts(self) -> dict[str, str]:
        # Reads prompts/greetings.yaml
    def get_guest_type_hints(self) -> dict[str, str]:
        # Reads prompts/guest_type_hints.yaml
    def build_context(self, speaker_name=None, memories=None, event=None,
                      phase_modifier=None, guest_context=None, **kwargs) -> list[dict]:
        # Returns list of message dicts [{"role": "system", "content": "..."}]
        # Assembles full prompt from character files + runtime state
        # Mirrors current mario_prompt.build_context() return type

    # Voice
    voice_config: VoiceConfig  # engine, model paths, rate, pitch
    pronunciation: dict        # word → phonetic map
    catchphrase_dir: Path

    # Visuals
    sprite_dir: Path
    ai_poses_dir: Path
    ai_pose_size: tuple[int, int]
    emotion_sprite_map: dict   # emotion → AI pose path
    state_sprite_map: dict     # state → AI pose path (or list)
    fallback_sprites: dict     # state → 2D sprite filename
    theme_colors: ThemeColors
    particle_colors: list[str]

    # Games
    def get_game_pools(self, shared_dir: Path) -> dict:
        # Loads character games/ + merges _shared/games/

    # Memory
    collections: dict          # faces/voices/memories → Qdrant collection names
    vip_profiles_dir: Path
```

### Data Flow

```
config.json  →  "character": "mario"
                       ↓
         CharacterLoader("characters", "mario")
                       ↓
          Reads characters/mario/character.yaml
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
          Server              Client
    - System prompt       - Sprites
    - TTS voice config    - Window title
    - Game pools          - Theme colors
    - Catchphrases        - Particle colors
    - Qdrant collections  - Branding text
```

### Integration Changes

**Server (`server/main.py`):**
- Replace hardcoded `SYSTEM_PROMPT` string with `char.get_system_prompt(context)`
- Replace hardcoded TTS config with `char.voice_config.*`
- Replace `CatchphraseBank(hardcoded_path)` with `CatchphraseBank(char.catchphrase_dir)`
- Replace hardcoded game pool imports with `char.get_game_pools(shared_dir)`
- Replace hardcoded Qdrant collection names with `char.collections["faces"]`, `char.collections["voices"]`, `char.collections["memories"]`

**Client (`client/mario_display.py`):**
- Replace `SPRITE_DIR` constant with `char.sprite_dir`
- Replace hardcoded window caption with `char.display_name`
- Replace hardcoded color constants with `char.theme_colors.*`
- Replace disco/particle color lists with `char.particle_colors`

**TTS (`server/tts.py`):**
- Move hardcoded `_preclean_tts_text` pronunciation subs to be loaded from `char.pronunciation`
- Keep the preclean function but make it accept a pronunciation dict parameter

**Games (`server/game_handlers.py`):**
- Move hardcoded pool constants to YAML files in character directory
- Load pools via `char.get_game_pools()` at startup
- Shared games loaded from `characters/_shared/games/`

### Shared Content Layer

`characters/_shared/` holds content used by all characters:
- Party events (shot events, party games)
- Universal games (Would You Rather, Truth or Dare, etc.)
- Common assets

Loading priority: character-specific content **merges with** shared content. If a character has `games/riddles.yaml` and `_shared/games/riddles.yaml` both exist, character-specific items are appended to shared items.

### Character Selection

- `config.json` gains a `"character"` field (default: `"mario"`)
- Both server and client read this field at startup
- Changing character requires server + client restart
- No hot-swap (simplest, most reliable)

### Migration Strategy

1. Create `characters/mario/` directory
2. Extract Mario content from code into character files
3. Build `CharacterLoader` class
4. Wire server to use loader instead of hardcoded values
5. Wire client to use loader instead of hardcoded values
6. Verify Mario works identically through the new system
7. Test with a minimal second character (e.g., "test_character") to validate

### Non-Goals (Future Sub-Projects)

These are explicitly deferred to separate design cycles:
- Voice training pipeline (training new RVC models from samples)
- Character creation UI (web interface for building characters)
- Hot-swap character switching at runtime
- Character marketplace / sharing platform

### Game Pool YAML Schemas

Each game type maps to a YAML file. All 20 pool types from current `game_handlers.py`:

```yaml
# games/trivia.yaml — list of {question, answer} objects
- question: "What is Mario's brother's name?"
  answer: "Luigi"

# games/reactions.yaml — categorized reaction text
rps_win: ["Wahoo! I win!", "Better luck next time!"]
rps_lose: ["Mama mia! You beat me!", "No way!"]
rps_tie: ["We think alike!", "Again, again!"]

# games/word_chains.yaml — flat string list
starter_words: ["mushroom", "princess", "castle"]

# games/simon.yaml — flat string list of actions
- "clap your hands"
- "stomp your feet"

# games/twenty_questions.yaml — list of {answer, category, hints} objects
- answer: "mushroom"
  category: "object"
  hints: ["It grows in dark places", "Mario loves to eat these", "It makes you bigger"]

# games/riddles.yaml — list of {q, a, hints} objects
- q: "I have a head and a tail but no body. What am I?"
  a: "coin"
  hints: ["Mario loves me", "I'm shiny", "Flip me to decide"]

# games/karaoke.yaml — flat string list of song titles
- "Bohemian Rhapsody"
- "Sweet Caroline"

# games/rapid_fire.yaml — flat string list of questions
- "Favorite color?"
- "Cats or dogs?"

# games/truth_or_dare.yaml — separate lists
truths: ["What's your most embarrassing moment?"]
dares: ["Do your best Mario impression!"]
bathroom_dares: ["Strike a pose in the mirror!"]

# games/would_you_rather.yaml — flat string list (full dilemma text)
- "Would you rather fight 100 Goombas or 1 giant Bowser?"

# games/wyr_extended.yaml — same format as would_you_rather
- "Would you rather have infinite coins or infinite lives?"

# games/hangman.yaml — flat string list of words/phrases
- "MUSHROOM KINGDOM"
- "PRINCESS PEACH"

# games/hot_takes.yaml — flat string list
- "Pineapple on pizza is actually amazing"

# games/name_that_character.yaml — list of {clues, answer} objects
- clues: ["Red hat", "Mustache", "Plumber"]
  answer: "Mario"

# games/story_starters.yaml — flat string list of story openings
- "It was a dark and stormy night in the Mushroom Kingdom..."

# games/nhie.yaml — flat string list (Never Have I Ever prompts)
- "Never have I ever eaten a Super Mushroom"
```

File-to-pool mapping: each YAML filename maps to a constant in `game_handlers.py`. The `CharacterLoader.get_game_pools()` method returns a dict keyed by pool name (e.g., `{"trivia": [...], "reactions": {...}, ...}`).

Shared games in `characters/_shared/games/` use the same formats. Merge rules:
- **List pools** (trivia, simon, etc.): character items appended to shared items
- **Dict pools** (reactions): character keys override shared keys; unspecified keys keep shared values
- Set `include_shared: false` in `character.yaml` to exclude shared content entirely

### Error Handling

**Fail-fast on startup:**
- Missing `characters/{name}/` directory → raise `CharacterNotFoundError` with helpful message listing available characters
- Missing `character.yaml` → raise `CharacterConfigError("character.yaml not found in ...")`
- Invalid YAML syntax → raise `CharacterConfigError` with yaml parse error details
- Missing required fields (identity.name, voice.preferred_engine) → raise `CharacterConfigError` listing missing fields

**Graceful degradation at runtime:**
- Missing sprite file → fall back to `fallback_sprites` mapping → fall back to a solid color rectangle
- Missing AI poses directory → fall back to legacy 2D sprites
- Missing catchphrase WAV → skip catchphrase (TTS engine handles it instead)
- Missing pronunciation entry → word passes through unmodified
- Missing game pool YAML → empty pool for that game type (shared pools still work)
- Missing prompt template variable → leave `{{variable}}` as literal text + log warning
- Missing VIP profile directory → empty VIP database (no VIP recognition)

**Validation on load:**
- `CharacterLoader.__init__()` validates all required fields exist
- Warns (doesn't crash) for optional missing files (sprites, catchphrases, lore)
- Logs a summary: "Loaded character 'Mario': 37 emotions, 65 catchphrases, 20 game pools, 3 VIP profiles"

### config.json Integration

Add `"character"` field to the existing config.json at the top level:

```json
{
  "character": "mario",
  "server": { ... },
  "client": { ... },
  ...
}
```

- Default value: `"mario"` (backward compatible)
- If field is missing, defaults to `"mario"`
- Both server and client read this field
- `characters_dir` is `./characters/` relative to project root
- Changing the character requires restarting both server and client

### Dependencies

- **PyYAML**: Must be added to both `server/requirements.txt` and project root `requirements.txt` (if exists). Client also needs it since `CharacterLoader` is shared.
- No other new dependencies required
