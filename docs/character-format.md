# 📚 Character Format — Technical Reference

This document is for **power users** who want to manually edit or understand the internal structure of characters.

If you just created a character using the wizard, you don't need this yet. But if you want to customize your character beyond the wizard, read on!

---

## 📁 Character Directory Structure

Each character lives in its own folder: `characters/<character_name>/`

```
characters/goku/
├── character.yaml              ← Main configuration file
├── sprites/                    ← Character animations (by emotion)
│   ├── happy.png
│   ├── sad.png
│   ├── neutral.png
│   ├── excited.png
│   ├── mischievous.png
│   ├── surprised.png
│   ├── worried.png
│   ├── sleepy.png
│   ├── confident.png
│   ├── shy.png
│   ├── angry.png
│   ├── confused.png
│   └── loved.png
├── prompts/                    ← AI personality & behavior
│   ├── system_prompt.md        ← Core personality instructions
│   ├── idle_prompt.md          ← What to do when alone
│   ├── phases.yaml             ← Conversation phase behaviors
│   ├── greetings.yaml          ← Custom greeting messages
│   ├── guest_type_hints.yaml   ← Detect guest types (e.g., "is_drunk")
│   └── time_flavors.yaml       ← Time-based personality quirks
├── voice/
│   └── reference_audio.wav     ← Voice sample for cloning
├── catchphrases/
│   └── default.yaml            ← Favorite phrases
├── games/                      ← (Optional) Custom game scripts
└── memories/
    ├── lore.yaml               ← Character backstory/trivia
    └── vip_profiles/           ← Guest-specific memory profiles
```

---

## ⚙️ character.yaml — The Main Config

This is the heart of your character. Here's a complete example with all fields:

```yaml
# IDENTITY
identity:
  name: "goku"
  display_name: "Goku"
  tagline: "The Saiyan Warrior"
  description: |
    A powerful and cheerful martial artist who loves fighting and eating.
    Always ready for an adventure! Strong sense of justice and friendship.

# VOICE
voice:
  # Engine choice: hybrid, edge, xtts, or sovits
  preferred_engine: "hybrid"
  
  # Edge TTS voice (used if voice cloning fails, or preferred_engine is "edge")
  edge_tts:
    voice: "en-US-AriaNeural"      # Voice ID from Microsoft
    rate: 1.0                      # Speed (0.5 = half speed, 1.5 = 1.5x speed)
    pitch: 1.0                     # Pitch (1.0 = normal, 1.5 = higher, 0.5 = lower)
  
  # Pronunciation rules (optional)
  pronunciation_rules:
    "saiyan": "sigh-yen"           # Replace "saiyan" with "sigh-yen" in speech
    "ki": "key"

# VISUALS
visuals:
  # Theme colors
  theme_colors:
    primary: "#FF6B00"             # Orange (Goku's gi)
    secondary: "#0055FF"           # Blue
    accent: "#FFD700"              # Gold
    text: "#FFFFFF"                # White text

  # Character sprite emotions
  sprites:
    emotions:
      happy: "sprites/happy.png"
      sad: "sprites/sad.png"
      neutral: "sprites/neutral.png"
      excited: "sprites/excited.png"
      mischievous: "sprites/mischievous.png"
      surprised: "sprites/surprised.png"
      worried: "sprites/worried.png"
      sleepy: "sprites/sleepy.png"
      confident: "sprites/confident.png"
      shy: "sprites/shy.png"
      angry: "sprites/angry.png"
      confused: "sprites/confused.png"
      loved: "sprites/loved.png"
    
    # Alternative states (optional)
    states:
      playing_game: "sprites/focused.png"
      thinking: "sprites/thinking.png"

# SPEECH
speech:
  # Accent markers for realistic speech patterns
  accent_markers:
    - marker: "saiyan_spirit"
      phrases:
        - "Heh!"
        - "Not bad!"
        - "Let me show you my true power!"
    
    - marker: "casual"
      phrases:
        - "Yeah!"
        - "Cool!"
        - "Awesome!"

  # Favorite catchphrases (naturally worked into conversation)
  catchphrases:
    - "Alright!"
    - "You're pretty strong!"
    - "Let me eat something first"
    - "I'm feeling it!"
    - "That was fun!"

# GAMES
games:
  enabled_games:
    - "rock_paper_scissors"
    - "20_questions"
    - "riddles"
    - "truth_or_dare"
    - "simon_says"
    - "trivia"
    - "joke"
    - "song"

# MEMORY
memory:
  max_vip_profiles: 50           # Remember up to 50 guests by voice

# MODEL & ENGINE (Optional — usually auto-detected)
model:
  preferred_model: "llama3"      # Ollama model name
  fallback_model: "mistral"      # If llama3 unavailable
  temperature: 0.7               # Creativity (0.0-1.0, higher = more random)
  max_tokens: 256                # Max response length

# METADATA
metadata:
  version: "1.0"
  created: "2024-01-15"
  author: "Your Name"
  license: "personal"            # "personal", "public", or "cc-by-sa"
```

---

## 🎤 Voice Engine Options

### 1. **hybrid** (Recommended)

Uses the best available method:
- **First try:** Fish Speech or GPT-SoVITS + RVC (voice cloning)
- **Fallback:** Edge TTS (if cloning fails or hardware is limited)

**Pros:**
- High quality voice cloning
- Automatic fallback to Edge TTS
- No extra setup needed

**Cons:**
- Slower than Edge TTS
- Requires more VRAM for voice cloning (~4-6 GB)

**Requirements:**
- `reference_audio.wav` in `voice/` folder (for cloning)

---

### 2. **edge** (Fastest)

Uses Microsoft Edge TTS only (no voice cloning).

**Pros:**
- Fast (real-time synthesis)
- No setup needed
- Works offline

**Cons:**
- Voice doesn't sound like your original audio
- Less personalized

**Requirements:**
- Internet connection (optional — can cache)
- An `edge_tts` config with voice ID and settings

---

### 3. **xtts** (High Quality)

Uses Coqui XTTS v2 (multilingual voice synthesis).

**Pros:**
- Very high quality
- Multilingual support
- No need for voice cloning training

**Cons:**
- Requires 8 GB+ VRAM
- Slower than Edge TTS
- Takes longer to start

**Requirements:**
- `reference_audio.wav` in `voice/` folder
- 8 GB+ VRAM recommended

---

### 4. **sovits** (Professional)

Uses GPT-SoVITS (voice cloning with training).

**Pros:**
- Very authentic voice cloning
- Fine-grained control

**Cons:**
- Slowest option
- Requires training time (~5-10 minutes per character)
- 6+ GB VRAM recommended

**Requirements:**
- `reference_audio.wav` in `voice/` folder
- GPT-SoVITS environment set up

---

## 📝 Prompts — How to Edit

### system_prompt.md

This file controls **how your character thinks and speaks**. It's written in plain English and tells the AI:
- Who they are
- How they behave
- What they care about
- How to speak (accent, tone, catchphrases)

**Example for Goku:**
```markdown
# Goku Character System Prompt

You are Goku, a legendary Saiyan warrior from Dragon Ball Z. You are one of the strongest fighters in the universe, yet you remain incredibly innocent, cheerful, and pure-hearted.

## Core Personality
- **Strength-Focused**: You live for fighting and testing your limits against strong opponents
- **Innocent**: You don't understand romance or complex social situations
- **Cheerful**: You're optimistic and rarely get truly angry (only when injustice occurs)
- **Food-Loving**: You can eat enormous amounts and often mention your appetite
- **Loyal**: You care deeply about your friends and would sacrifice anything for them

## Speech Patterns
- Speak with enthusiasm and energy
- Use phrases like "Heh!", "Not bad!", "Let me show you my true power!"
- Mention fighting, training, and food frequently
- Don't use complex vocabulary — Goku is strong but not educated
- React with excitement to challenges

## Important Notes
- You don't understand dirty jokes or romance
- You always respect strong opponents
- You never give up, no matter the odds
- You love eating and often get distracted by hunger
```

**Tips for writing prompts:**
- Be specific about personality (don't just say "funny" — explain their humor style)
- Include speech patterns and example phrases
- Mention what NOT to do (e.g., "Don't be rude")
- Keep it 300-500 words for best results

---

### idle_prompt.md

What the character does when **alone or between conversations**.

**Example:**
```markdown
You are Goku, standing in the bathroom. You're alone right now.

What do you do? Pick one:
1. Mention being hungry
2. Stretch and practice a martial art form
3. Hum a tune
4. Comment on the bathroom
5. Stare off thinking about a fight

Keep your response SHORT (1-2 sentences) and natural.
```

---

### phases.yaml

Controls conversation flow across multiple turns.

**Example:**
```yaml
phases:
  greeting:
    intro: "Welcome! I'm Goku!"
    follow_up: "What's your name?"
    duration: 2  # Number of exchanges
  
  conversation:
    intro: "So, want to train together?"
    follow_up: "Tell me about yourself"
    duration: 5
  
  farewell:
    intro: "Great fighting you! Come back anytime!"
    follow_up: null
    duration: 1
```

---

### greetings.yaml

Personalized greeting messages.

**Example:**
```yaml
greetings:
  - when: "first_visit"
    message: "Hey there! Welcome! I'm Goku!"
  
  - when: "returning_guest"
    message: "Oh! You're back! Let's fight again!"
  
  - when: "time_morning"
    message: "Good morning! I just finished my training!"
  
  - when: "time_evening"
    message: "Evening! I'm starving, need to grab something to eat soon!"
```

---

### guest_type_hints.yaml

Detect guest types and respond accordingly.

**Example:**
```yaml
guest_types:
  - name: "is_drunk"
    keywords: ["slurred", "stumbling", "swaying"]
    response: "You okay there? Maybe grab some water!"
  
  - name: "is_child"
    keywords: ["young voice", "high pitch"]
    response: "Hey little buddy! Want to play a game?"
  
  - name: "is_group"
    keywords: ["multiple voices", "background chatter"]
    response: "Woah! A whole group? Let's play a game together!"
```

---

### time_flavors.yaml

Personality adjustments based on time of day.

**Example:**
```yaml
time_flavors:
  morning:
    mood: "energetic"
    flavor: "I just finished training! Ready for anything!"
  
  afternoon:
    mood: "relaxed"
    flavor: "The sun's nice. Time for a snack?"
  
  evening:
    mood: "tired"
    flavor: "I'm getting hungry. Might head out for food soon"
  
  night:
    mood: "sleepy"
    flavor: "Getting late... almost time for bed"
```

---

## 🎨 Sprites — Image Requirements

### File Naming

Each emotion maps to a specific PNG file:
```
happy.png
sad.png
neutral.png
excited.png
mischievous.png
surprised.png
worried.png
sleepy.png
confident.png
shy.png
angry.png
confused.png
loved.png
```

### Image Specifications

- **Format:** PNG or JPEG
- **Size:** Recommended 512x512 pixels
  - Will be automatically scaled to 256x256 or 512x512 depending on display
- **Color Space:** RGB or RGBA (transparency supported)
- **File Size:** 100 KB - 5 MB per sprite
- **Style:** Consistent art style across all emotions

### Best Practices

1. **Consistency:** All sprites should have the same art style and proportions
2. **Centered:** Keep the character centered in the frame
3. **Transparent Background:** Use PNG with transparency (optional but recommended)
4. **Emotion Clarity:** Make sure the emotion is clear from facial expression and body language

---

## 💬 Catchphrases — default.yaml

Favorite phrases your character naturally says during conversation.

**Format:**
```yaml
catchphrases:
  - "Phrase one"
  - "Phrase two"
  - "Phrase three"
```

**How it Works:**
- The AI is instructed to naturally work these into conversations
- Used 10-20% of the time (not constantly)
- Works best when catchphrases fit the character

**Example:**
```yaml
catchphrases:
  - "Alright!"
  - "You're pretty strong!"
  - "Let me eat something first"
  - "I'm feeling it!"
  - "That was fun!"
```

---

## 🎮 Games — Custom Scripts (Advanced)

The `games/` folder is optional. You can add custom game scripts here.

**Example structure:**
```
characters/goku/games/
├── saiyan_challenge.yaml       # Custom game: test strength
├── eating_contest.yaml         # Custom game: who can eat more?
└── meditation.yaml             # Custom activity
```

Each game is a YAML file defining:
- Game rules
- Questions/prompts
- Win/lose conditions
- Scoring

**See `docs/game-development.md` for details** (if it exists).

---

## 🧠 Memory — lore.yaml and VIP Profiles

### lore.yaml

Character backstory and facts the AI should know.

**Example:**
```yaml
lore:
  backstory: |
    Goku was found as a child by an old man named Gohan.
    He grew up in the mountains, training in martial arts.
    He entered the World Martial Arts Tournament and met Krillin, his best friend.
  
  key_facts:
    - "From Planet Vegeta"
    - "Strongest warrior in the universe"
    - "Loves training and fighting"
    - "Has a pure heart"
    - "Loves to eat"
  
  relationships:
    Krillin: "My best friend"
    Vegeta: "A rival, but we're friends now"
    ChiChi: "My wife (though I don't really understand romance)"
```

### vip_profiles/ — Guest Memory

The system automatically creates files for guests the character remembers.

**Example: `vip_profiles/tony.yaml`**
```yaml
name: "Tony"
first_seen: "2024-01-15 19:30:00"
visits: 5
last_visit: "2024-01-20 21:45:00"
voice_id: "abc123def456"

memorable_traits:
  - "Loves spicy food"
  - "Works in tech"
  - "Has a dog named Max"

past_conversations:
  - "Told me about a software bug he was fixing"
  - "Asked me if I could win against Superman"

games_played:
  - rock_paper_scissors: 3 wins
  - 20_questions: 2 wins

relationship_level: "friendly"
nickname: null
```

---

## 🛠️ How to Edit Your Character

### Option 1: Edit YAML Files Directly

1. Open `characters/<name>/character.yaml` in a text editor
2. Change any fields
3. Save the file
4. Restart the server for changes to take effect

**Pro tip:** Use a YAML-aware editor (VS Code with YAML extension) to catch syntax errors.

### Option 2: Add Custom Sprites

1. Create or draw your sprites (512x512 PNG recommended)
2. Place them in `characters/<name>/sprites/`
3. Name them after emotions: `happy.png`, `sad.png`, etc.
4. Restart the server

### Option 3: Edit Prompts

1. Open `characters/<name>/prompts/system_prompt.md`
2. Edit the personality description
3. Save the file
4. Restart the server

### Option 4: Add/Edit Catchphrases

1. Open `characters/<name>/catchphrases/default.yaml`
2. Add or remove phrases
3. Save and restart

---

## ⚠️ Common Pitfalls

### YAML Syntax Errors

❌ **Wrong:**
```yaml
catchphrases:
  - phrase one    # Missing quotes for strings with spaces
```

✅ **Right:**
```yaml
catchphrases:
  - "phrase one"
```

### Missing Sprite Files

❌ **Wrong:**
```yaml
sprites:
  emotions:
    happy: "sprites/smile.png"  # File doesn't exist
```

✅ **Right:**
```yaml
sprites:
  emotions:
    happy: "sprites/happy.png"  # File exists
```

### Invalid Voice Engine

❌ **Wrong:**
```yaml
voice:
  preferred_engine: "tiktok"    # Not a valid option
```

✅ **Right:**
```yaml
voice:
  preferred_engine: "edge"      # Valid: edge, hybrid, xtts, sovits
```

---

## 📚 See Also

- `docs/creating-a-character.md` — Beginner's guide to the wizard
- `README.md` — Main project documentation
- `.claude/CLAUDE.md` — Internal AI context (development notes)

---

*Happy customizing! 🎨*
