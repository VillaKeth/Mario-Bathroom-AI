# server/shot_events.py
"""Generalized Shot Event system for party ceremonies and toasts."""
import os
from dataclasses import dataclass, field
from typing import Optional
import re
import logging

logger = logging.getLogger("shot_events")

DEBUG_SHOT_EVENTS = os.environ.get("DEBUG_SHOT_EVENTS", "").lower() in ("1", "true", "yes")

@dataclass
class ShotEvent:
    name: str
    tone: str  # "solemn", "celebratory", "fun"
    trigger_type: str  # "auto", "voice", "admin"
    display_name: str = ""  # Human-readable name for on-screen display
    voice_keywords: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=lambda: ["announcement", "countdown", "toast", "recovery"])
    announcement_text: str = ""
    silence_text: str = ""  # only for solemn events
    toast_text: str = ""
    recovery_line: str = ""
    countdown: bool = True
    music_file: Optional[str] = None
    music_duration: int = 0
    skip_key: Optional[str] = None  # e.g., "ctrl+shift+l"
    image_file: Optional[str] = None  # event-specific image shown during phases
    fired: bool = False

class ShotEventManager:
    def __init__(self):
        self.events: dict[str, ShotEvent] = {}
        self._active_event: Optional[str] = None
        self._countdown_cache: dict[str, bytes] = {}
        if DEBUG_SHOT_EVENTS:
            print("[DEBUG_SHOT_EVENTS] ShotEventManager: initialized")
    
    def register(self, event: ShotEvent):
        self.events[event.name] = event
        if DEBUG_SHOT_EVENTS:
            print(f"[DEBUG_SHOT_EVENTS] register: {event.name} ({event.tone})")
    
    def trigger(self, name: str) -> dict:
        if name not in self.events:
            return {"status": "not_found", "event": name}
        event = self.events[name]
        if event.fired:
            return {"status": "already_fired", "event": name}
        if self._active_event is not None:
            return {"status": "blocked_by_active", "event": name, "active": self._active_event}
        event.fired = True
        self._active_event = name
        if DEBUG_SHOT_EVENTS:
            print(f"[DEBUG_SHOT_EVENTS] trigger: {name}")
        return {"status": "triggered", "event": name}
    
    def complete(self, name: str):
        if self._active_event == name:
            self._active_event = None
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] complete: {name}")
    
    def reset(self, name: str):
        if name in self.events:
            # Block reset if event is currently running
            if self._active_event == name:
                if DEBUG_SHOT_EVENTS:
                    print(f"[DEBUG_SHOT_EVENTS] reset BLOCKED: {name} is currently active")
                return False
            self.events[name].fired = False
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] reset: {name}")
            return True
        return False
    
    def check_voice_trigger(self, text: str) -> Optional[ShotEvent]:
        lower = text.lower()
        for event in self.events.values():
            if event.fired or event.trigger_type not in ("voice", "auto"):
                continue
            for kw in event.voice_keywords:
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', lower):
                    if DEBUG_SHOT_EVENTS:
                        print(f"[DEBUG_SHOT_EVENTS] voice_trigger: '{kw}' matched for {event.name}")
                    return event
        return None
    
    def list_events(self) -> list[dict]:
        return [{"name": e.name, "fired": e.fired, "tone": e.tone}
                for e in self.events.values()]
    
    def get_countdown_texts(self) -> list[str]:
        return [
            "Ten!", "Nine!", "Eight!", "Seven!", "Six!",
            "Five!", "Four!", "Three!", "Two!", "One!"
        ]
    
    async def precache_countdown_audio(self, tts_func):
        """Pre-cache TTS audio for all countdown numbers at startup."""
        self._countdown_cache = {}
        for text in self.get_countdown_texts():
            try:
                audio = await tts_func(text)
                self._countdown_cache[text] = audio
                if DEBUG_SHOT_EVENTS:
                    print(f"[DEBUG_SHOT_EVENTS] precached countdown: {text}")
            except Exception as e:
                print(f"[DEBUG_SHOT_EVENTS] ERROR precaching '{text}': {e}")
    
    def get_cached_countdown(self, text: str):
        """Return pre-cached audio for a countdown number, or None."""
        return self._countdown_cache.get(text)
    
    @property
    def is_active(self) -> bool:
        return self._active_event is not None
    
    @property
    def active_event(self) -> Optional[ShotEvent]:
        if self._active_event:
            return self.events.get(self._active_event)
        return None

def create_default_events() -> ShotEventManager:
    """Load shot events from server/data/shot_events.json.
    
    To add a new event, just copy-paste an entry in shot_events.json.
    See docs/EVENTS.md for a full guide.
    """
    import json
    
    mgr = ShotEventManager()
    config_path = os.path.join(os.path.dirname(__file__), "data", "shot_events.json")
    
    if not os.path.isfile(config_path):
        print(f"[SHOT_EVENTS] WARNING: {config_path} not found — no events loaded")
        return mgr
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"[SHOT_EVENTS] ERROR loading {config_path}: {e}")
        return mgr
    
    events_list = config.get("events", [])
    for entry in events_list:
        try:
            music_file = entry.get("music_file")
            music_duration = entry.get("music_duration", 0)
            
            # Auto-detect MP3 duration from file if not specified or set to 0
            if music_file and music_duration <= 0:
                music_duration = _get_audio_duration(music_file)
            elif music_file:
                # Even if duration is set, verify against actual file and warn if off
                actual = _get_audio_duration(music_file)
                if actual > 0 and abs(actual - music_duration) > 10:
                    logger.info(f"[SHOT_EVENTS] {entry['name']}: overriding music_duration {music_duration}s → {actual}s (from file)")
                    music_duration = actual
            
            event = ShotEvent(
                name=entry["name"],
                tone=entry.get("tone", "fun"),
                trigger_type=entry.get("trigger_type", "voice"),
                display_name=entry.get("display_name", entry["name"]),
                voice_keywords=entry.get("voice_keywords", []),
                phases=entry.get("phases", ["announcement", "countdown", "toast", "recovery"]),
                announcement_text=entry.get("announcement_text", ""),
                silence_text=entry.get("silence_text", ""),
                toast_text=entry.get("toast_text", ""),
                recovery_line=entry.get("recovery_line", ""),
                countdown=entry.get("countdown", True),
                music_file=music_file,
                music_duration=int(music_duration),
                skip_key=entry.get("skip_key"),
                image_file=entry.get("image_file"),
            )
            mgr.register(event)
        except KeyError as e:
            print(f"[SHOT_EVENTS] Skipping event with missing field: {e}")
        except Exception as e:
            print(f"[SHOT_EVENTS] Error loading event: {e}")
    
    print(f"[SHOT_EVENTS] Loaded {len(mgr.events)} events from {config_path}")
    return mgr


def _get_audio_duration(file_path: str) -> int:
    """Get audio file duration in seconds. Returns 0 if file not found or unreadable."""
    # Resolve relative paths from project root
    if not os.path.isabs(file_path):
        project_root = os.path.dirname(os.path.dirname(__file__))
        file_path = os.path.join(project_root, file_path)
    
    if not os.path.isfile(file_path):
        logger.warning(f"[SHOT_EVENTS] Music file not found: {file_path}")
        return 0
    
    try:
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        duration = int(audio.info.length) + 1  # Round up
        logger.info(f"[SHOT_EVENTS] Auto-detected duration: {file_path} = {duration}s")
        return duration
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[SHOT_EVENTS] mutagen failed for {file_path}: {e}")
    
    # Fallback: estimate from file size (128kbps assumption)
    try:
        size_bytes = os.path.getsize(file_path)
        estimated = int(size_bytes / (128 * 1024 / 8)) + 5  # Add 5s buffer
        logger.info(f"[SHOT_EVENTS] Estimated duration from file size: {file_path} ≈ {estimated}s")
        return estimated
    except Exception:
        return 0
