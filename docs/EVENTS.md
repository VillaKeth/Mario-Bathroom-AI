# 🎉 Adding Custom Shot Events

Shot events are party ceremonies where Mario leads the group through a toast, countdown, and celebration. They can be solemn memorials, birthday surprises, or fun themed events.

## Quick Start — Add a New Event in 60 Seconds

1. Open `server/data/shot_events.json`
2. Copy-paste the template below into the `"events"` array
3. Fill in your details
4. (Optional) Add a music file and image
5. Restart the server

## Template

```json
{
  "name": "my_event_name",
  "display_name": "Display Name On Screen",
  "tone": "fun",
  "trigger_type": "voice",
  "voice_keywords": ["my event", "do the thing"],
  "phases": ["announcement", "countdown", "toast", "recovery"],
  "announcement_text": "What Mario says to get everyone's attention.",
  "toast_text": "What Mario says for the actual toast. Raise your glasses!",
  "recovery_line": "What Mario says to bring the party back after the toast.",
  "countdown": true,
  "music_file": "client/assets/audio/my_song.mp3",
  "music_duration": 60,
  "image_file": "client/assets/images/my_image.png"
}
```

## Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Unique internal ID (snake_case, no spaces) |
| `display_name` | ❌ | Name shown on screen. Use `\n` for line breaks |
| `tone` | ❌ | `"solemn"`, `"fun"`, or `"celebratory"` (affects overlay colors) |
| `trigger_type` | ❌ | `"voice"` (say keywords), `"auto"` (timer), or `"admin"` (manual only) |
| `voice_keywords` | ❌ | Phrases that trigger the event when spoken/typed |
| `phases` | ❌ | Order of ceremony. See Phases below |
| `announcement_text` | ❌ | Mario's attention-getting speech |
| `silence_text` | ❌ | Text during moment of silence (solemn events only) |
| `toast_text` | ❌ | The actual toast speech |
| `recovery_line` | ❌ | What Mario says to transition back to the party |
| `countdown` | ❌ | `true`/`false` — whether to count down from 10 |
| `music_file` | ❌ | Path to MP3 played during music phase |
| `music_duration` | ❌ | How long to play music (seconds) |
| `skip_key` | ❌ | Keyboard shortcut to skip (e.g., `"ctrl+shift+l"`) |
| `image_file` | ❌ | Image shown during the event overlay |

## Available Phases

Phases run in order. Pick and choose which ones you want:

| Phase | What Happens |
|-------|-------------|
| `announcement` | Mario speaks `announcement_text` to get attention |
| `silence` | Moment of silence (5 seconds quiet). Uses `silence_text` |
| `countdown` | Mario counts down from 10 ("TEN-a! NINE-a!...") |
| `toast` | Mario speaks `toast_text`. Everyone drinks! |
| `music` | Plays `music_file` for `music_duration` seconds |
| `recovery` | Mario speaks `recovery_line` to bring party back |

### Example Phase Combos

- **Quick toast**: `["announcement", "countdown", "toast", "recovery"]`
- **Solemn memorial**: `["announcement", "silence", "countdown", "toast", "music", "recovery"]`
- **Just music**: `["announcement", "music", "recovery"]`

## Triggering Events

### Voice Trigger
Anyone says one of the `voice_keywords` during conversation and Mario will start the event.

### Admin Trigger
Use the pygame client admin command:
```
/memorial <event_name>
```
Or hit the API directly:
```bash
curl -X POST http://localhost:8765/admin/shot_event/my_event_name
```

### Auto Trigger
Events with `"trigger_type": "auto"` fire automatically based on party timer (configured in server code).

## Adding Music & Images

### Music
1. Place your MP3 in `client/assets/audio/` or `client/assets/music/`
2. Set `music_file` to the relative path: `"client/assets/audio/my_song.mp3"`
3. Set `music_duration` to how many seconds to play

### Images
1. Place your image (PNG/JPG) in `client/assets/images/`
2. Set `image_file` to the relative path: `"client/assets/images/my_image.png"`
3. Image displays during the announcement, silence, and toast phases

## Example: Deltarune Event

Here's the existing Deltarune event as a reference:

```json
{
  "name": "deltarune",
  "display_name": "Deltarune",
  "tone": "fun",
  "trigger_type": "voice",
  "voice_keywords": ["deltarune shot", "shot for deltarune", "deltarune toast"],
  "phases": ["announcement", "countdown", "toast", "music", "recovery"],
  "announcement_text": "Attention everyone! Mario has a very special toast! This one goes out to the heroes of the Dark World, Deltarune!",
  "toast_text": "Calling all heroes! Kris, that's you Roman! Ralsei, that's you Elijah! Susie, that's you Villa! And the one and only Lancer, that's the birthday boy Jacob! Raise your glasses, to Deltarune!",
  "recovery_line": "WAHOO! What a fun game! Now back to the party!",
  "countdown": true,
  "music_file": "client/assets/audio/deltarune_hopes_dreams.mp3",
  "music_duration": 90,
  "image_file": "client/assets/images/deltarune.png"
}
```

## Example: Creating a "Smash Bros" Event

Want Mario to lead a Smash Bros toast? Here's how:

1. Find a Smash Bros song (MP3) → save as `client/assets/audio/smash_theme.mp3`
2. Find a Smash Bros image (PNG) → save as `client/assets/images/smash_bros.png`
3. Add this to `server/data/shot_events.json`:

```json
{
  "name": "smash_bros",
  "display_name": "Super Smash Bros",
  "tone": "fun",
  "trigger_type": "voice",
  "voice_keywords": ["smash bros shot", "smash toast", "smash brothers"],
  "phases": ["announcement", "countdown", "toast", "music", "recovery"],
  "announcement_text": "WAHOO! Everyone listen up! It's time for a SMASH BROTHERS toast! This one goes out to the greatest fighters in the multiverse!",
  "toast_text": "Link, Samus, Pikachu, Kirby, and of course, the one and only MARIO! EVERYONE IS HERE! Raise your glasses, to SMASH BROS!",
  "recovery_line": "GAME! And the winner is... ALL OF US! Back to the party!",
  "countdown": true,
  "music_file": "client/assets/audio/smash_theme.mp3",
  "music_duration": 60,
  "image_file": "client/assets/images/smash_bros.png"
}
```

4. Restart the server. Say "smash bros shot" to trigger it!
