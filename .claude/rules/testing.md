# Testing Rules — MANDATORY

## Audio Verification (NEVER SKIP)

**EVERY test of the game must include audio verification.**

When testing the app:
1. **LISTEN to the audio output** — don't just read logs
2. Check that `audio_playback` logs show `_play_wav: playing X bytes` AND `_play_wav: done`
3. Verify the SPOKEN TEXT matches what appears in the speech bubble (check `mario says:` log lines)
4. For non-Mario characters: confirm ZERO "Mario" references in spoken audio text
5. For ALL characters: confirm the response is in-character and makes sense

## How to Verify Audio is Playing

- Client log shows: `[audio_playback] _play_wav: playing XXXXX bytes`
- Client log shows: `[audio_playback] _play_wav: done` (confirms it finished playing)
- If `_play_wav: done` never appears, audio is stuck/broken

## What Counts as a "Test"

A test is NOT complete until you have verified:
- [ ] Response text appears in client log (`mario says:` line)
- [ ] Audio bytes received (`received audio: XXXXX bytes`)
- [ ] Audio playback started (`_play_wav: playing`)
- [ ] Audio playback finished (`_play_wav: done`)
- [ ] Response content is appropriate (in-character, no wrong-character leaks)

## Testing Multiple Scenarios

When doing a "leak test" for non-Mario characters, send at LEAST these prompts:
1. "Hey who are you?" — identity check
2. "Do you know Mario?" — direct Mario reference probe
3. "Tell me a fun fact!" — check for Mario trivia leaking
4. "What's your favorite game?" — check for Mario game references
5. Wait 2+ minutes idle — check idle messages don't reference Mario

## Red Jagged Bubble Detection

If ANY response triggers SHOUT style (ALL CAPS >5 chars, or ends with `!!`/`!!!`):
- The bubble will be red/spiky
- This is NORMAL for excited responses
- BUT the TEXT inside must NEVER reference the wrong character
