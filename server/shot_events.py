# server/shot_events.py
"""Generalized Shot Event system for party ceremonies and toasts."""
from dataclasses import dataclass, field
from typing import Optional
import re

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
            self.events[name].fired = False
            if self._active_event == name:
                self._active_event = None
            if DEBUG_SHOT_EVENTS:
                print(f"[DEBUG_SHOT_EVENTS] reset: {name}")
    
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
    """Create the three party shot events."""
    mgr = ShotEventManager()
    
    mgr.register(ShotEvent(
        name="lisa_webb_memorial",
        tone="solemn",
        trigger_type="auto",
        voice_keywords=["lisa", "aunt lisa", "lisa webb", "toast to lisa"],
        phases=["announcement", "silence", "countdown", "toast", "music", "recovery"],
        announcement_text="Everyone, please. Mario has something important to say. Tonight we remember someone very special, Lisa Webb. She was family to Jacob, and she's watching over this party from above.",
        silence_text="Let's have a moment of silence for Lisa Webb.",
        toast_text="Now raise your glasses, everyone. To Lisa Webb, a beautiful soul who touched all of our lives. To Lisa!",
        recovery_line="Lisa would've loved this party. Now let's keep celebrating in her honor!",
        countdown=True,
        music_file="client/assets/audio/lisa_memorial.mp3",
        music_duration=120,
        skip_key="ctrl+shift+l",
    ))
    
    mgr.register(ShotEvent(
        name="birthday_boy",
        tone="celebratory",
        trigger_type="voice",
        voice_keywords=["birthday shot", "shot for jacob", "birthday boy shot"],
        phases=["announcement", "countdown", "toast", "recovery"],
        announcement_text="It's-a time to take a shot for the BIRTHDAY BOY! Jacob Hoppenstedt, this one's for YOU!",
        toast_text="To Jacob! Happy Birthday! WAHOO!",
        recovery_line="WAHOO! Now THAT'S how we party!",
        countdown=True,
    ))
    
    mgr.register(ShotEvent(
        name="deltarune",
        tone="fun",
        trigger_type="voice",
        voice_keywords=["deltarune shot", "shot for deltarune", "deltarune toast"],
        phases=["announcement", "countdown", "toast", "recovery"],
        announcement_text="This shot goes out to the heroes of the Dark World!",
        toast_text="Kris! Susie! Ralsei! And the one and only LANCER! Jacob voiced Lancer, and Keth voiced Susie! To Deltarune!",
        recovery_line="Haha! What a fun-a game! Now back to the party!",
        countdown=True,
    ))
    
    return mgr
