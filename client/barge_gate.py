"""Pure voice barge-in gate (no audio deps).

While the character speaks, the mic keeps capturing. This gate learns the
echo floor (what the mic hears of our own speakers) and fires only when the
mic runs sustained-louder than that floor by a margin — i.e. a human talking
over the character. No AEC; an energy gate with hysteresis is enough for a
bathroom kiosk.
"""


class BargeGate:
    def __init__(self, margin: float = 2.5, sustain_s: float = 0.8,
                 floor_alpha: float = 0.05, abs_min: float = 0.015,
                 cooldown_s: float = 2.0):
        self.margin = float(margin)
        self.sustain_s = float(sustain_s)
        self.floor_alpha = float(floor_alpha)
        self.abs_min = float(abs_min)
        self.cooldown_s = float(cooldown_s)
        self.echo_floor = 0.0
        self._loud_run_s = 0.0
        self._cooldown_left = 0.0

    @property
    def threshold(self) -> float:
        """Current trigger threshold: echo floor scaled, never below abs_min."""
        return max(self.abs_min, self.echo_floor * self.margin)

    def reset(self):
        self._loud_run_s = 0.0

    def update(self, rms: float, chunk_s: float, playing: bool) -> bool:
        """Feed one mic chunk's RMS. Returns True exactly when a barge fires.

        The echo floor only learns from below-threshold chunks so the user's
        own voice never trains the gate shut.
        """
        if self._cooldown_left > 0.0:
            self._cooldown_left = max(0.0, self._cooldown_left - chunk_s)
        if not playing:
            self._loud_run_s = 0.0
            return False
        if self.echo_floor <= 0.0 and rms > 0.0:
            # Bootstrap: the first audible playing chunk defines the echo floor
            # (playback onset is speakers-only; nobody has barged yet). Without
            # this, bleed louder than abs_min could never train the gate and
            # steady echo alone would fire it.
            self.echo_floor = rms
            return False
        if rms < self.threshold:
            # Learn the speaker bleed while it is quietly steady.
            self.echo_floor = ((1.0 - self.floor_alpha) * self.echo_floor
                               + self.floor_alpha * rms)
            self._loud_run_s = 0.0
            return False
        self._loud_run_s += chunk_s
        if self._loud_run_s >= self.sustain_s and self._cooldown_left <= 0.0:
            self._loud_run_s = 0.0
            self._cooldown_left = self.cooldown_s
            return True
        return False
