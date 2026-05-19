# server/shot_events.py
"""Generalized Shot Event system for party ceremonies and toasts."""
import os
from dataclasses import dataclass, field
from typing import Optional
import re

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
            "TEN-a!", "NINE-a!", "EIGHT-a!", "SEVEN-a!", "SIX-a!",
            "FIVE-a!", "FOUR-a!", "THREE-a!", "TWO-a!", "ONE-a!"
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
                music_file=entry.get("music_file"),
                music_duration=entry.get("music_duration", 0),
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
