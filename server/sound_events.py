"""Sound Event Manager — Nintendo-style SFX on key moments.

Maps game events to WAV files and plays them non-blocking.
Gracefully degrades if no WAV files are present.
"""

import logging
import os
import threading

logger = logging.getLogger("sound-events")

# Default event → filename mapping
DEFAULT_EVENT_MAP = {
    "greeting": "coin.wav",
    "game_start": "powerup.wav",
    "roast": "fireball.wav",
    "vomit": "pipe.wav",
    "farewell": "star.wav",
    "birthday": "1up.wav",
    "correct": "coin.wav",
    "wrong": "pipe.wav",
    "level_up": "powerup.wav",
    "victory": "star.wav",
    "challenge": "powerup.wav",
    "milestone": "1up.wav",
    "gossip": "coin.wav",
    "memorial": "memorial.wav",
    "toast": "victory.wav",
}


class SoundEventManager:
    """Fire-and-forget sound effects triggered by game events."""

    def __init__(self, sfx_dir: str | None = None, event_map: dict[str, str] | None = None):
        self._sfx_dir = sfx_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "sfx"
        )
        self._char_sfx_dir: str | None = None  # per-character override dir
        self._event_map = event_map or dict(DEFAULT_EVENT_MAP)
        self._mixer_ready = False
        self._available_files: dict[str, str] = {}  # event_name → full path

        self._scan_files()
        self._init_mixer()

    def set_character_sfx_dir(self, char_sfx_dir: str | None):
        """Point at a character's own SFX folder (characters/<char>/sfx/).
        Per-event WAVs there OVERRIDE the shared generic set, so each character
        can have its own non-Mario sounds. Missing files fall back to shared."""
        self._char_sfx_dir = char_sfx_dir if (char_sfx_dir and os.path.isdir(char_sfx_dir)) else None
        self._scan_files()

    def _scan_files(self):
        """Scan sfx directories for available WAVs. Character dir wins over shared."""
        self._available_files = {}
        search_note = self._sfx_dir
        if not os.path.isdir(self._sfx_dir) and not self._char_sfx_dir:
            logger.info(f"SFX directory not found: {self._sfx_dir} — sound events disabled")
            return

        for event_name, filename in self._event_map.items():
            # Character override first, then shared generic
            for base in (self._char_sfx_dir, self._sfx_dir):
                if not base:
                    continue
                full_path = os.path.join(base, filename)
                if os.path.isfile(full_path):
                    self._available_files[event_name] = full_path
                    break

        n_char = sum(1 for p in self._available_files.values()
                     if self._char_sfx_dir and p.startswith(self._char_sfx_dir))
        logger.info(f"Sound events: {len(self._available_files)}/{len(self._event_map)} WAVs "
                    f"loaded ({n_char} character-specific from {self._char_sfx_dir or 'none'}, "
                    f"rest from {search_note})")

    def _init_mixer(self):
        """Initialize pygame mixer if available and files exist."""
        if not self._available_files:
            return
        try:
            import pygame.mixer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._mixer_ready = True
            logger.info("pygame.mixer initialized for sound effects")
        except ImportError:
            logger.info("pygame not installed — sound events will log only")
        except Exception as e:
            logger.warning(f"pygame.mixer init failed: {e} — sound events will log only")

    def is_available(self) -> bool:
        """True if any WAV files were found (regardless of mixer status)."""
        return len(self._available_files) > 0

    def get_available_events(self) -> list[str]:
        """Return list of events that have WAV files available."""
        return list(self._available_files.keys())

    def trigger(self, event_name: str):
        """Play sound effect for an event. Non-blocking, fire-and-forget."""
        if event_name not in self._event_map:
            logger.debug(f"Unknown sound event: {event_name}")
            return

        if event_name not in self._available_files:
            logger.debug(f"No WAV for event '{event_name}' — skipping")
            return

        if not self._mixer_ready:
            logger.debug(f"Sound event '{event_name}' triggered (no mixer — log only)")
            return

        # Non-blocking playback in a thread
        path = self._available_files[event_name]
        t = threading.Thread(target=self._play, args=(path, event_name), daemon=True)
        t.start()

    def _play(self, path: str, event_name: str):
        """Actually play the WAV file (called from thread)."""
        try:
            import pygame.mixer
            sound = pygame.mixer.Sound(path)
            sound.play()
            logger.debug(f"Playing SFX: {event_name} → {os.path.basename(path)}")
        except Exception as e:
            logger.warning(f"SFX playback failed for {event_name}: {e}")

    def trigger_websocket(self, event_name: str) -> dict | None:
        """Return a WebSocket message dict for client-side playback instead of server-side.

        Use this when the client handles audio playback.
        Returns None if event is unknown.
        """
        if event_name not in self._event_map:
            return None
        return {
            "type": "sound_effect",
            "event": event_name,
            "filename": self._event_map.get(event_name, ""),
        }
