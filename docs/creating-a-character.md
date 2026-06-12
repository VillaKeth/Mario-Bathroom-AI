# 🎨 Creating a Character — Beginner's Guide

Welcome! This guide walks you through creating your own custom AI party character using the **Character Creator Wizard** — no coding required.

---

## 📋 What You Need

Before you start, make sure you have:

- **Python 3.10 or higher** — [Install from python.org](https://python.org/downloads)
- **Ollama** (recommended, but optional) — [Install from ollama.ai](https://ollama.ai)
  - Ollama runs local AI models for character personalities
  - If you skip it, characters will use Edge TTS voice synthesis instead
- **This repository cloned** — See the main README.md for setup

---

## 🚀 Quick Start

### Option 1: Automatic (Recommended)

After running `setup.bat` (Windows) or `./setup.sh` (Mac/Linux):

- If no characters exist, the **Character Creator Wizard** opens automatically
- Follow the steps below to create your character

### Option 2: Manual Launch

**Windows:**
```
create_character.bat
```

**Mac / Linux:**
```bash
./create_character.sh
```

---

## 🧙 Walk Through the Wizard

The wizard guides you through 6 steps. Each one is explained below.

### Step 1: 🆔 Identity

**What it does:** Name your character and give them a personality description.

**Fields:**
- **Character Name** — What is your character called? (e.g., "Goku", "Elsa", "Pikachu")
- **Display Name** — How should the UI show their name? (usually same as Character Name)
- **Tagline** — A short, catchy phrase (e.g., "The Saiyan Warrior" or "Let it go!")
- **Description** — A few sentences describing who they are (e.g., "A legendary warrior who loves eating and training")

**Auto-Fill Feature:** The wizard recognizes some popular characters (Mario, Yoshi, Luigi, etc.) and can auto-fill their info. If your character matches a known one, the wizard will suggest it.

**Example:**
```
Name: Goku
Display Name: Goku
Tagline: The Saiyan Warrior
Description: A powerful and cheerful martial artist who loves fighting and eating. Always ready for an adventure!
```

---

### Step 2: 💬 Personality

**What it does:** Define how your character speaks and behaves.

**Fields:**
- **System Prompt** — The AI personality instructions (e.g., "You are a cheerful pirate who uses 'arr' in every sentence")
  - This is what tells the AI how to stay in character
  - Make it descriptive but concise (1-2 paragraphs)
- **Accent Markers** — Special speech patterns (e.g., `pirate: "arr", "matey"`, `southern: "y'all", "howdy"`)
  - Optional: Leave blank if your character doesn't have a special accent
- **Catchphrases** — Favorite phrases your character says (e.g., "It's-a me, Mario!" or "UNLIMITED POWER!")
  - Separate each with a comma
  - The character will naturally work these into conversations

**Example:**
```
System Prompt:
You are Goku, a legendary Saiyan warrior from Dragon Ball. You are incredibly strong, cheerful, and innocent. You love fighting, eating, and helping your friends. You speak with enthusiasm and often get distracted by thoughts of food and battle. You respect strong opponents and never give up.

Accent Markers:
- saiyan_spirit: "Heh!", "Not bad!", "Let me show you my true power!"

Catchphrases:
Alright!, You're pretty strong!, Let me eat something first, I'm feeling it!, That was fun!
```

---

### Step 3: 🎤 Voice

**What it does:** Choose or upload your character's voice.

**Options:**

1. **Upload Audio File** — Use your own voice or a voice sample
   - Supported formats: `.wav`, `.mp3`, `.ogg`
   - For best results: 3-10 seconds of clear voice

2. **Record Live** — Record your character's voice in real-time
   - Press the button and speak for 3-10 seconds
   - Great for voice acting or quick demos

3. **Pick an Edge TTS Voice** — Pre-made digital voices
   - No training required
   - Options include: American accents, British, Australian, and more
   - Adjustable pitch and speed

**Behind the Scenes:**
- If you upload or record audio, the system uses it to **clone the voice** (GPT-SoVITS + RVC)
- If you pick Edge TTS, it uses that pre-built voice
- Both sound great! Use whichever fits your character.

**Example:**
- Goku: Upload a recording of someone doing Goku's voice, or pick a young male Edge TTS voice
- Elsa: Pick "Microsoft Zira Desktop" (or similar female voice) from Edge TTS

---

### Step 4: 🎨 Appearance

**What it does:** Design your character's look (sprite animations for different emotions).

**Options:**

1. **AI-Generate Sprites** — Let AI create sprite sheets automatically
   - Uses Stable Diffusion to generate images based on your character description
   - Fast (takes ~30 seconds per emotion)
   - Works offline (no API calls)

2. **Upload Your Own Sprites** — Use custom artwork
   - Provide PNG images for each emotion
   - Recommended size: 512x512 pixels (will be scaled to fit)

**Emotions Included:**
- Happy, Sad, Neutral, Excited, Mischievous, Surprised, Worried, Sleepy, Confident, Shy, Angry, Confused, Loved

**Tips:**
- If using AI generation, the character description from Step 1 is used as the prompt
- If uploading, name your images clearly: `happy.png`, `sad.png`, etc.
- Consistency is key — all sprites should have a similar art style and size

**Example:**
- Goku: AI-generate orange-haired warrior in martial arts gi
- Custom character: Upload hand-drawn sprites in your favorite style

---

### Step 5: ⚙️ Hardware & Models

**What it does:** Pick an AI model and voice engine that fits your hardware.

**Model Selection:**
- **Available Models:**
  - `llama3` — Fast, good for real-time conversation (default, 4.7 GB)
  - `mistral` — Smaller, faster, but less capable (1.3 GB)
  - `neural-chat` — Optimized for chat (4.9 GB)
  - Custom: Point to any Ollama model you've already pulled

- **GPU Memory Requirement:**
  - The wizard auto-detects your GPU and recommends the best model
  - If you have <6 GB VRAM, it suggests a smaller model
  - If you have >10 GB VRAM, it recommends the best quality option

**Voice Engine Selection:**
- **hybrid** — Best quality (uses Fish Speech or Edge TTS + voice cloning)
- **edge** — Edge TTS only (requires internet, fast)
- **xtts** — High-quality voice synthesis (offline, 8 GB+ VRAM recommended)
- **sovits** — GPT-SoVITS voice cloning (slower but very authentic)

**Tips:**
- Lower-spec PCs? Use `mistral` model + `edge` voice engine
- Gaming PC? Use `llama3` + `hybrid` for best quality
- The wizard gives recommendations based on your system

---

### Step 6: ✅ Review & Create

**What it does:** Preview everything and create your character.

**Review Checklist:**
- ✓ Character name and tagline look good?
- ✓ Personality description is accurate?
- ✓ Voices and sprites preview correctly?
- ✓ Model and engine selections match your hardware?

**If Everything Looks Good:**
- Click **"Create Character"**
- The wizard creates a new folder: `characters/<name>/`
- All character data is saved there

**If Something's Wrong:**
- Click **"Back"** to edit previous steps
- Wizard saves your progress — you won't lose anything

---

## 📁 After Creation: Your Character Folder

Once your character is created, a new folder appears:

```
characters/goku/
├── character.yaml          ← Main config file (can edit later)
├── sprites/                ← Character images (by emotion)
│   ├── happy.png
│   ├── sad.png
│   ├── neutral.png
│   └── ... (other emotions)
├── prompts/                ← AI personality instructions
│   ├── system_prompt.md
│   ├── idle_prompt.md
│   ├── phases.yaml
│   └── ... (other prompt files)
├── voice/
│   └── reference_audio.wav ← Voice sample used for cloning
└── catchphrases/
    └── default.yaml        ← Favorite phrases
```

See `docs/character-format.md` for detailed info on editing these files directly.

---

## 🎮 Start Using Your Character

**The easy way — one double-click:**
```bash
start.bat                 # Windows
./start.sh                # Mac/Linux
```
This starts the server AND opens the character window for you. A window appears
with your character on screen.

**Interact with them:**
- Type and press Enter (or speak, if a mic is connected)
- Press 1–8 to start a game, F1 for help, F5 for party mode
- They respond out loud in their own voice and personality!

> Advanced: `start_server.bat` (brain only) and `start_client.bat` (window only)
> exist if you ever want to run them separately. Most people never need to.

---

## 🆘 Troubleshooting

### "Ollama not running" Error

**Problem:** The wizard says Ollama isn't available.

**Solutions:**
- Install Ollama from [ollama.ai](https://ollama.ai)
- Restart your terminal after installing
- On Mac/Linux, make sure Ollama is in your PATH: `which ollama`
- You can skip this warning and use Edge TTS instead (less immersive but works offline)

### VRAM Error ("Out of Memory")

**Problem:** Voice cloning or sprite generation fails with a memory error.

**Solutions:**
- Choose a smaller model in Step 5 (e.g., `mistral` instead of `llama3`)
- Use `edge` voice engine instead of `hybrid`
- Close other GPU-heavy apps (games, video editing, etc.)
- If you have an older GPU (<4 GB VRAM), stick with Edge TTS

### Port Conflict ("Address already in use")

**Problem:** Server won't start — port 8765 is already taken.

**Solutions:**
- Kill the old process:
  ```bash
  # Windows:
  netstat -ano | findstr 8765
  taskkill /PID <pid> /F

  # Mac/Linux:
  lsof -i :8765
  kill -9 <PID>
  ```
- Then start the server again

### Voice Sounds Robotic or Bad

**Problem:** Character's voice quality is poor.

**Solutions:**
- **If using voice cloning:** Make sure your audio sample (Step 3) is clear, with no background noise
- **If using Edge TTS:** Try a different voice preset in Step 5
- **Check Ollama:** Make sure `ollama serve` is running in the background
- **Fallback:** The system automatically falls back to Edge TTS if voice cloning fails

### Character Images Don't Show

**Problem:** Sprites aren't displaying in the client.

**Solutions:**
- Make sure sprites are PNG or JPEG format
- Check sprite file sizes are reasonable (100 KB - 5 MB each)
- Try re-generating sprites: Run the wizard again and choose "AI-Generate"
- Check `characters/<name>/sprites/` — do the files exist?

---

## 💡 Tips & Tricks

### Create Multiple Characters

Run the wizard again to create as many characters as you want:
```bash
create_character.bat          # Windows
./create_character.sh         # Mac/Linux
```

Each gets its own folder in `characters/`.

### Edit a Character Later

**Edit via YAML:**
1. Open `characters/<name>/character.yaml` in a text editor
2. Change any fields (name, personality, etc.)
3. Save the file
4. Restart the server

**See `docs/character-format.md` for all editable fields.**

### Backup Your Characters

Your characters are in `characters/`. Back them up:
```bash
# Windows:
xcopy characters characters_backup /E /I

# Mac/Linux:
cp -r characters characters_backup
```

### Share Characters

Zip up a character folder and share it:
```bash
# Windows:
# Right-click characters/<name>/ → Send to → Compressed folder

# Mac/Linux:
tar -czf goku.tar.gz characters/goku/
```

Someone else can extract it into their `characters/` folder and use it immediately.

---

## 🎉 You're Done!

Congratulations — your character is ready! 🎊

Next steps:
- Start the server and client (see above)
- Play games with your character
- Customize further by editing `character.yaml` (see `docs/character-format.md`)
- Create more characters and build your own party!

**Questions?** Check the main README.md or open an issue on GitHub.

---

*Happy character creating! 🚀*
