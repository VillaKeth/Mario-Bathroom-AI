"""Pure helpers for group-mode speaker camera-cuts.

The server tags each group line with speaker_id; the client defers that line's
presentation (bubble, name, sprite set) until its WAV starts playing, then
"cuts" the single-sprite display to the speaker. These helpers hold the
decision logic so it unit-tests without pygame.
"""


def should_defer(metadata) -> bool:
    """A group line (speaker_id present) is presented at audio start, not at
    message arrival — the previous speaker may still be talking."""
    return bool((metadata or {}).get("speaker_id"))


def cut_plan(cache: dict, current_id, speaker_id):
    """Decide what a cut needs: (apply, cache_entry).

    apply=False when there is nothing to do (same speaker, no id) or nothing
    to do it with (member not preloaded — keep the current sprites, never
    crash the draw loop).
    """
    if not speaker_id or speaker_id == current_id:
        return False, None
    entry = (cache or {}).get(speaker_id)
    return (entry is not None), entry


def backlog_label(speaker, text) -> str:
    """Chat-backlog line for a group utterance: name-prefixed so the F3
    history reads like a script."""
    if speaker:
        return f"[{speaker}] {text}"
    return text
