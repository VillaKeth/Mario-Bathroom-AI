"""GuestProfile system — unified guest identity management.

In-memory guest profiles that link voice, face, and mood into unified identities.
Thread-safe with RLock. Clears on server restart (new party night).
"""
import os
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Debug flag following existing patterns
DEBUG_GUEST_PROFILES = os.environ.get("DEBUG_GUEST_PROFILES", "").lower() in ("1", "true", "yes")

# Greeting debounce timeout in seconds
GREETING_COOLDOWN = 60


@dataclass
class MoodEntry:
    """Single mood entry in a guest's history."""
    timestamp: datetime
    emotion: str
    energy: float  # 0.0 to 1.0


@dataclass
class GuestProfile:
    """Unified guest identity linking voice, face, and mood."""
    name: str
    guest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    voice_id: Optional[str] = None
    face_ids: list[str] = field(default_factory=list)
    visit_count: int = 1
    total_interactions: int = 0
    mood_history: list[MoodEntry] = field(default_factory=list)
    topics_discussed: list[str] = field(default_factory=list)
    is_active: bool = True
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)

    @property
    def current_mood(self) -> str:
        """Get current emotion from latest mood entry, or 'neutral' if none."""
        if not self.mood_history:
            return "neutral"
        return self.mood_history[-1].emotion

    @property
    def current_energy(self) -> float:
        """Get current energy from latest mood entry, or 0.5 if none."""
        if not self.mood_history:
            return 0.5
        return self.mood_history[-1].energy

    @property
    def mood_trend(self) -> str:
        """Analyze mood trend from recent entries: 'improving', 'declining', or 'stable'."""
        if len(self.mood_history) < 2:
            return "stable"
        
        # Compare first and last energy in last 3 entries
        recent_entries = self.mood_history[-3:]
        if len(recent_entries) < 2:
            return "stable"
        
        first_energy = recent_entries[0].energy
        last_energy = recent_entries[-1].energy
        energy_diff = last_energy - first_energy
        
        if energy_diff > 0.15:
            return "improving"
        elif energy_diff < -0.15:
            return "declining"
        else:
            return "stable"


class GuestProfileManager:
    """Thread-safe manager for guest profiles and identity linking."""

    def __init__(self):
        self._lock = threading.RLock()
        self._profiles: dict[str, GuestProfile] = {}
        self._voice_map: dict[str, str] = {}  # voice_id → name
        self._face_map: dict[str, str] = {}   # face_id → name
        self._mystery_counter: int = 0
        self._last_greeted: dict[str, datetime] = {}  # for greeting debounce
        
        if DEBUG_GUEST_PROFILES:
            print("[DEBUG_GUEST_PROFILES] GuestProfileManager: initialized")

    def identify_by_voice(self, name: str, voice_id: str) -> GuestProfile:
        """Identify guest by voice, creating new profile if needed."""
        with self._lock:
            # Check voice_map first
            if voice_id in self._voice_map:
                existing_name = self._voice_map[voice_id]
                profile = self._profiles[existing_name]
                profile.total_interactions += 1
                profile.last_seen = datetime.now()
                profile.is_active = True
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] identify_by_voice: returning existing {existing_name} by voice_id")
                return profile
            
            # Check if profile exists by name
            if name in self._profiles:
                profile = self._profiles[name]
                profile.voice_id = voice_id
                profile.total_interactions += 1
                profile.last_seen = datetime.now()
                profile.is_active = True
                self._voice_map[voice_id] = name
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] identify_by_voice: linked voice_id to existing {name}")
                return profile
            
            # Create new profile
            profile = GuestProfile(name=name, voice_id=voice_id, total_interactions=1)
            self._profiles[name] = profile
            self._voice_map[voice_id] = name
            
            if DEBUG_GUEST_PROFILES:
                print(f"[DEBUG_GUEST_PROFILES] identify_by_voice: created new profile {name}")
            return profile

    def identify_by_face(self, name: str, face_id: str) -> GuestProfile:
        """Identify guest by face, creating new profile if needed."""
        with self._lock:
            # Check face_map first
            if face_id in self._face_map:
                existing_name = self._face_map[face_id]
                profile = self._profiles[existing_name]
                profile.total_interactions += 1
                profile.last_seen = datetime.now()
                profile.is_active = True
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] identify_by_face: returning existing {existing_name} by face_id")
                return profile
            
            # Check if profile exists by name
            if name in self._profiles:
                profile = self._profiles[name]
                if face_id not in profile.face_ids:
                    profile.face_ids.append(face_id)
                profile.total_interactions += 1
                profile.last_seen = datetime.now()
                profile.is_active = True
                self._face_map[face_id] = name
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] identify_by_face: linked face_id to existing {name}")
                return profile
            
            # Create new profile
            profile = GuestProfile(name=name, face_ids=[face_id], total_interactions=1)
            self._profiles[name] = profile
            self._face_map[face_id] = name
            
            if DEBUG_GUEST_PROFILES:
                print(f"[DEBUG_GUEST_PROFILES] identify_by_face: created new profile {name}")
            return profile

    def create_mystery_guest(self) -> GuestProfile:
        """Create a mystery guest with auto-generated name."""
        with self._lock:
            self._mystery_counter += 1
            name = f"Mystery Guest #{self._mystery_counter}"
            profile = GuestProfile(name=name)
            self._profiles[name] = profile
            
            if DEBUG_GUEST_PROFILES:
                print(f"[DEBUG_GUEST_PROFILES] create_mystery_guest: created {name}")
            return profile

    def rename_guest(self, old_name: str, new_name: str) -> GuestProfile:
        """Rename a guest, updating all mappings."""
        with self._lock:
            if old_name not in self._profiles:
                raise ValueError(f"Guest '{old_name}' not found")
            
            profile = self._profiles[old_name]
            profile.name = new_name
            
            # Update _profiles dict
            self._profiles[new_name] = profile
            del self._profiles[old_name]
            
            # Update voice_map
            if profile.voice_id and profile.voice_id in self._voice_map:
                self._voice_map[profile.voice_id] = new_name
            
            # Update face_map
            for face_id in profile.face_ids:
                if face_id in self._face_map:
                    self._face_map[face_id] = new_name
            
            if DEBUG_GUEST_PROFILES:
                print(f"[DEBUG_GUEST_PROFILES] rename_guest: {old_name} → {new_name}")
            return profile

    def record_mood(self, name: str, emotion: str, energy: float):
        """Record a mood entry for a guest."""
        with self._lock:
            if name in self._profiles:
                mood_entry = MoodEntry(
                    timestamp=datetime.now(),
                    emotion=emotion,
                    energy=energy
                )
                self._profiles[name].mood_history.append(mood_entry)
                
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] record_mood: {name} → {emotion} ({energy})")

    def record_topic(self, name: str, topic: str):
        """Record a topic discussed by a guest (no duplicates)."""
        with self._lock:
            if name in self._profiles:
                if topic not in self._profiles[name].topics_discussed:
                    self._profiles[name].topics_discussed.append(topic)
                    
                    if DEBUG_GUEST_PROFILES:
                        print(f"[DEBUG_GUEST_PROFILES] record_topic: {name} → {topic}")

    def guest_entered(self, name: str):
        """Mark guest as active and increment visit count."""
        with self._lock:
            if name in self._profiles:
                profile = self._profiles[name]
                if not profile.is_active:
                    profile.visit_count += 1
                profile.is_active = True
                profile.last_seen = datetime.now()
                
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] guest_entered: {name} (visit #{profile.visit_count})")

    def guest_exited(self, name: str):
        """Mark guest as inactive."""
        with self._lock:
            if name in self._profiles:
                self._profiles[name].is_active = False
                
                if DEBUG_GUEST_PROFILES:
                    print(f"[DEBUG_GUEST_PROFILES] guest_exited: {name}")

    def get_active_guests(self) -> list[str]:
        """Get list of currently active guest names."""
        with self._lock:
            return [name for name, profile in self._profiles.items() if profile.is_active]

    def get_guest_context(self, name: str) -> str:
        """Build human-readable context string for a guest."""
        with self._lock:
            if name not in self._profiles:
                return "Unknown guest"
            
            profile = self._profiles[name]
            
            # Basic info
            context_parts = [f"Guest: {profile.name}"]
            
            # Confirmation status
            confirmations = []
            if profile.voice_id:
                confirmations.append("voice-confirmed")
            if profile.face_ids:
                confirmations.append("face-confirmed")
            if confirmations:
                context_parts.append(f"({', '.join(confirmations)}, visit #{profile.visit_count})")
            else:
                context_parts.append(f"(visit #{profile.visit_count})")
            
            # Current mood info
            if profile.mood_history:
                mood_info = f"Current mood: {profile.current_mood} (energy: {profile.current_energy}, trend: {profile.mood_trend})"
                context_parts.append(mood_info)
            
            # Topics discussed
            if profile.topics_discussed:
                topics_str = ", ".join(profile.topics_discussed)
                context_parts.append(f"Topics discussed: {topics_str}")
            
            # Other active guests
            other_active = [n for n in self.get_active_guests() if n != name]
            if other_active:
                others_str = ", ".join(other_active)
                context_parts.append(f"Also in bathroom: {others_str}")
            
            return ". ".join(context_parts) + "."

    def register_vip(self, name: str, voice_id: Optional[str] = None, face_id: Optional[str] = None):
        """Pre-register a VIP guest."""
        with self._lock:
            if name in self._profiles:
                profile = self._profiles[name]
            else:
                profile = GuestProfile(name=name)
                self._profiles[name] = profile
            
            if voice_id:
                profile.voice_id = voice_id
                self._voice_map[voice_id] = name
            
            if face_id and face_id not in profile.face_ids:
                profile.face_ids.append(face_id)
                self._face_map[face_id] = name
            
            if DEBUG_GUEST_PROFILES:
                print(f"[DEBUG_GUEST_PROFILES] register_vip: {name}")

    def should_greet(self, name: str) -> bool:
        """Check if guest should be greeted (60s debounce)."""
        with self._lock:
            now = datetime.now()
            last_greeted = self._last_greeted.get(name)
            
            if last_greeted is None or (now - last_greeted).total_seconds() >= GREETING_COOLDOWN:
                self._last_greeted[name] = now
                return True
            
            return False