# server/shot_events.py
"""Generalized Shot Event system for party ceremonies and toasts."""
from dataclasses import dataclass, field
from typing import Optional

DEBUG_SHOT_EVENTS = True

@dataclass
class ShotEvent:
    name: str
    tone: str  # "solemn", "celebratory", "fun"
    trigger_type: str  # "auto", "voice", "admin"
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
        event.fired = True
        self._active_event = name
        if DEBUG_SHOT_EVENTS:
            print(f"[DEBUG_SHOT_EVENTS] trigger: {name}")
        return {"status": "triggered", "event": name}
    
    def complete(self, name: str):
        if name in self.events:
            self._active_event = None
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] complete: {name}")
    
    def reset(self, name: str):
        if name in self.events:
            self.events[name].fired = False
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] reset: {name}")
    
    def check_voice_trigger(self, text: str) -> Optional[ShotEvent]:
        lower = text.lower()
        for event in self.events.values():
            if event.fired or event.trigger_type not in ("voice", "auto"):
                continue
            for kw in event.voice_keywords:
                if kw.lower() in lower:
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
            audio = await tts_func(text)
            self._countdown_cache[text] = audio
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] precached countdown: {text}")
    
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
