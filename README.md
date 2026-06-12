# 🎉 AI Party Character Bot

Make your own talking AI character for a party. It greets people, jokes, plays
games, sings, remembers guests, and shows an animated character on screen with a
real voice. Mario, Reze, March 7th, your own original character — anyone.

Think **"local character.ai you can run on one computer."** You build a character
in a point-and-click wizard (no coding), then press Start and talk to them.

---

## ⭐ Run it in 3 steps (start here)

You need a Windows or Mac/Linux computer and about 15 minutes. That's it.

### Step 1 — Install (once)
Double-click **`setup.bat`** (Windows) or run **`./setup.sh`** (Mac/Linux).
It installs everything automatically. Grab a coffee — first time takes a few minutes.

> Don't have Python yet? Install **Python 3.10+** from [python.org](https://www.python.org/downloads/)
> first, and **check the box "Add Python to PATH"** during install. That's the only
> manual thing you ever have to do.

### Step 2 — Make your character (the Wizard)
Double-click **`create_character.bat`** (Windows) or run **`./create_character.sh`**.
Your web browser opens the **Character Creator Wizard**. Fill in the boxes:

1. **Identity** — name + a one-line description ("a sarcastic purple rabbit").
2. **Personality** — how they act.
3. **Voice** — click **🔎 Auto-find Voice** to pull a real voice from YouTube, or upload a clip.
4. **Appearance** — describe how they look; the wizard draws all their sprites.
5. **Hardware** — it auto-detects your computer; just click Next.
6. **Review & Create** — also set the **Event name** here (e.g. "Sarah's Birthday").
7. **Generate Content** — it writes their jokes, games, and lines.

When it finishes, your character is 100% ready. No files to edit.

### Step 3 — Start the party
Double-click **`start.bat`** (Windows) or run **`./start.sh`** (Mac/Linux).
A window opens with your character on screen. Type to them (or talk if you have a mic)
and they respond out loud. **Done.**

---

## 🕹️ The launcher buttons (what each file does)

| Double-click this | What it does |
|---|---|
| **`setup.bat`** / `setup.sh` | Installs everything. Run once. |
| **`create_character.bat`** / `.sh` | Opens the Character Creator Wizard in your browser. |
| **`start.bat`** / `start.sh` | **The play button.** Starts everything and shows your character. |
| `start_server.bat` / `.sh` | Advanced: starts just the brain (server). |
| `start_client.bat` / `.sh` | Advanced: starts just the on-screen window. |

99% of the time you only ever touch **setup → create_character → start**.

---

## 🗣️ Talking to your character

- **Type** in the window and press Enter.
- **Talk** out loud if a microphone is connected (it listens automatically).
- Press number keys **1–8** for instant games/jokes/songs.
- Press **F1** to see all the keyboard shortcuts.
- Press **F5** for party mode (dancing + lights).

---

## 🎨 Adding your own art & sounds (optional, still no coding)

Everything is in the wizard's **Sprite Manager** (the 🎨 button, or visit
`http://localhost:8766/sprites` while the wizard is open):

- **Sprites** — auto-generated, or generate/upload better ones per emotion.
- **Backgrounds** — generate or upload a scene; set one as the default.
- **Sound effects** — drop `.wav` files in `characters/<name>/sfx/` to replace the
  default sounds (each character can have its own; defaults are generic, not Mario).

Want premium hand-made sprites? Generate images in ChatGPT/etc., drop them in
`characters/<name>/_incoming/` named by pose (e.g. `positive_happy.png`), and run
`scripts/import_sprites.py <name>` — it removes the background and installs them.

---

## 🖥️ What computer do I need?

It runs on almost anything and **auto-detects** your hardware:

| Your computer | What you get |
|---|---|
| Big GPU (12 GB+ VRAM) | Best quality, fast, custom trained voices |
| Mid GPU (6–8 GB) | Good quality |
| Small GPU / laptop (4 GB) | Works, but voices/answers are slower; close other apps for best results |
| No GPU | Works on CPU, slower |

A 24 GB GPU box runs everything buttery smooth. A small 4 GB laptop works too —
just give it room (close Chrome/Teams while it runs).

---

## ❓ Something went wrong?

| Problem | Fix |
|---|---|
| `setup` says Python not found | Install Python 3.10+ and re-tick "Add Python to PATH", reboot. |
| Wizard page won't open | Make sure `create_character.bat` is still running; open `http://localhost:8766`. |
| Character won't talk / slow | On a small GPU, close other apps (browsers, Teams) to free memory. |
| No voice, only text | Normal on first run while the voice engine warms up; give it a minute. |
| It feels stuck | Close the windows and run `start.bat` again — it cleans up old copies itself. |

---

## 🧠 For tinkerers (you do NOT need any of this)

- **[QUICKSTART.md](QUICKSTART.md)** — the shortest possible path.
- **[Creating a Character](docs/creating-a-character.md)** — wizard walk-through.
- **[Character Format](docs/character-format.md)** — manual YAML/prompt/sprite editing.
- **[Deployment Guide](docs/deployment-guide.md)** — running it at a real party.
- **[Events & Music](docs/EVENTS.md)** · **[Music Guide](docs/MUSIC_GUIDE.md)**
- **[Mixed Image Generation](docs/mixed_image_gen_plan.md)** — premium image providers.
- `.claude/CLAUDE.md` — full architecture reference.

Characters live in `characters/<name>/`. Settings live in `config.json`.
Nothing about the system is Mario-specific anymore — every character is isolated,
so one character never leaks another's lines, voice, or sounds.
