"""Mario sound effects generator using Pygame and synthesized tones."""

import os
import math
import logging
import numpy as np
import pygame

DEBUG_SFX = True
logger = logging.getLogger(__name__)


class SoundEffects:
    """Generates and plays Mario-style sound effects using synthesized audio."""

    def __init__(self):
        self._sounds = {}
        self._initialized = False

    def init(self):
        """Initialize pygame mixer and generate sound effects."""
        if DEBUG_SFX:
            logger.info("[DEBUG_SFX] SoundEffects.init: START")

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self._initialized = True
        except Exception as e:
            logger.error(f"[DEBUG_SFX] Failed to init mixer: {e}")
            return

        self._generate_sounds()
        if DEBUG_SFX:
            logger.info(f"[DEBUG_SFX] SoundEffects.init: generated {len(self._sounds)} sounds")

    def _make_tone(self, frequency: float, duration: float, volume: float = 0.3,
                   fade_out: bool = True, wave_type: str = "square") -> pygame.mixer.Sound:
        """Generate a tone as a pygame Sound object."""
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, n_samples, dtype=np.float32)

        if wave_type == "sine":
            wave = np.sin(2 * math.pi * frequency * t)
        elif wave_type == "square":
            wave = np.sign(np.sin(2 * math.pi * frequency * t))
        elif wave_type == "triangle":
            wave = 2 * np.abs(2 * (frequency * t - np.floor(frequency * t + 0.5))) - 1
        else:
            wave = np.sin(2 * math.pi * frequency * t)

        if fade_out:
            fade = np.linspace(1.0, 0.0, n_samples)
            wave *= fade

        wave = (wave * volume * 32767).astype(np.int16)
        return pygame.mixer.Sound(buffer=wave.tobytes())

    def _make_multi_tone(self, notes: list, volume: float = 0.3) -> pygame.mixer.Sound:
        """Generate a sequence of notes. Each note is (frequency, duration)."""
        sample_rate = 44100
        segments = []

        for freq, dur in notes:
            n_samples = int(sample_rate * dur)
            t = np.linspace(0, dur, n_samples, dtype=np.float32)
            wave = np.sign(np.sin(2 * math.pi * freq * t))
            # Quick fade at end to avoid clicks
            fade_samples = min(200, n_samples // 4)
            wave[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples)
            segments.append(wave)

        full = np.concatenate(segments)
        full = (full * volume * 32767).astype(np.int16)
        return pygame.mixer.Sound(buffer=full.tobytes())

    def _generate_sounds(self):
        """Generate all Mario-style sound effects."""

        # Coin sound — two quick high notes
        self._sounds["coin"] = self._make_multi_tone([
            (988, 0.08),   # B5
            (1319, 0.35),  # E6
        ], volume=0.25)

        # 1-Up sound — ascending notes
        self._sounds["oneup"] = self._make_multi_tone([
            (330, 0.08),   # E4
            (392, 0.08),   # G4
            (523, 0.08),   # C5
            (659, 0.08),   # E5
            (784, 0.08),   # G5
            (1047, 0.2),   # C6
        ], volume=0.25)

        # Mushroom/power-up sound — ascending glide
        self._sounds["powerup"] = self._make_multi_tone([
            (262, 0.06), (294, 0.06), (330, 0.06), (349, 0.06),
            (392, 0.06), (440, 0.06), (494, 0.06), (523, 0.06),
            (587, 0.06), (659, 0.12),
        ], volume=0.2)

        # Pipe/warp sound — descending
        self._sounds["pipe"] = self._make_multi_tone([
            (523, 0.08), (494, 0.08), (440, 0.08), (392, 0.08),
            (349, 0.08), (330, 0.08), (294, 0.15),
        ], volume=0.2)

        # Jump sound — quick ascending
        self._sounds["jump"] = self._make_multi_tone([
            (200, 0.04), (300, 0.04), (400, 0.04), (500, 0.08),
        ], volume=0.15)

        # Star power — fast repeating high notes
        self._sounds["star"] = self._make_multi_tone([
            (784, 0.06), (880, 0.06), (988, 0.06), (1047, 0.06),
            (988, 0.06), (880, 0.06), (784, 0.06), (880, 0.06),
            (988, 0.06), (1047, 0.12),
        ], volume=0.2)

        # Fireball — quick descending
        self._sounds["fireball"] = self._make_multi_tone([
            (800, 0.03), (600, 0.03), (400, 0.05), (200, 0.08),
        ], volume=0.15)

        # Death/sad sound — descending slow
        self._sounds["sad"] = self._make_multi_tone([
            (392, 0.15), (349, 0.15), (330, 0.15), (262, 0.3),
        ], volume=0.2)

        # Flag/victory — ascending fanfare
        self._sounds["victory"] = self._make_multi_tone([
            (262, 0.1), (330, 0.1), (392, 0.1), (523, 0.15),
            (660, 0.1), (784, 0.3),
        ], volume=0.25)

        # Enter/greeting — cheerful ding
        self._sounds["greeting"] = self._make_multi_tone([
            (523, 0.1), (659, 0.1), (784, 0.2),
        ], volume=0.2)

        # Exit/goodbye — gentle descend
        self._sounds["goodbye"] = self._make_multi_tone([
            (784, 0.1), (659, 0.1), (523, 0.2),
        ], volume=0.2)

        # Thinking — repeating soft tones
        self._sounds["thinking"] = self._make_multi_tone([
            (440, 0.15), (0.1, 0.05), (494, 0.15), (0.1, 0.05),
            (440, 0.15),
        ], volume=0.1)

    def play(self, sound_name: str):
        """Play a sound effect by name."""
        if not self._initialized:
            return

        sound = self._sounds.get(sound_name)
        if sound:
            if DEBUG_SFX:
                logger.info(f"[DEBUG_SFX] play: {sound_name}")
            sound.play()
        else:
            logger.warning(f"[DEBUG_SFX] play: unknown sound '{sound_name}'")

    @property
    def available_sounds(self) -> list:
        return list(self._sounds.keys())
