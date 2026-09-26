"""Readout rates -> one behavior.

Mean firing rate per neuron (Hz) of each readout population over the window
decides; rules run in priority order and the first match wins. REJECT is
"tasted bitter and did not extend the proboscis": a bitter taste while MN9
stayed under the feeding threshold (the brain's own arbitration).

"Tasted bitter" is the bitter stimulus delivered this window (`stim`), not the
measured bitter-GRN rate, so activity that reaches the GRN axon terminals from
inside the brain is never read as a taste (the first build's engine drove them
to ~46 Hz with nothing tasted; the Shiu-faithful engine reads 0 Hz there).
Without `stim` the measured rate stands in for the taste.
"""
from dataclasses import dataclass

DEFAULT_THRESHOLDS = {"escape_hz": 50.0, "feed_hz": 80.0, "bitter_hz": 20.0,
                      "groom_hz": 30.0, "walk_hz": 20.0}
EMOTION = {"ESCAPE": "scared", "REJECT": "disgusted", "FEED": "happy",
           "GROOM": "neutral", "WALK": "curious", "NOTHING": "neutral"}
POSE = {"ESCAPE": "movement/escape", "REJECT": "negative/reject", "FEED": "positive/feeding",
        "GROOM": "reactions/grooming", "WALK": "movement/walking", "NOTHING": "neutral/idle"}


@dataclass(frozen=True)
class Behavior:
    name: str
    intensity: float = 0.0
    direction: str = ""      # WALK only: "forward" | "back"

    @property
    def emotion(self):
        return EMOTION[self.name]

    @property
    def pose(self):
        return POSE[self.name]


def _intensity(rate, threshold):
    return round(max(0.0, min(1.0, rate / (3.0 * threshold))), 3)


def classify(rates, thresholds=None, stim=None):
    """stim: {sense population: Hz} delivered this window, if known."""
    th = dict(DEFAULT_THRESHOLDS)
    th.update({k: float(v) for k, v in (thresholds or {}).items() if k in th})

    def r(k):
        return float((rates or {}).get(k, 0.0) or 0.0)

    taste = r("bitter") if stim is None else float(stim.get("bitter", 0.0) or 0.0)
    if r("escape") >= th["escape_hz"]:
        return Behavior("ESCAPE", _intensity(r("escape"), th["escape_hz"]))
    if taste >= th["bitter_hz"] and r("feed") < th["feed_hz"]:
        return Behavior("REJECT", _intensity(taste, th["bitter_hz"]))
    if r("feed") >= th["feed_hz"]:
        return Behavior("FEED", _intensity(r("feed"), th["feed_hz"]))
    if r("groom") >= th["groom_hz"]:
        return Behavior("GROOM", _intensity(r("groom"), th["groom_hz"]))
    walk, back = r("walk"), r("backup")
    if max(walk, back) >= th["walk_hz"]:
        return Behavior("WALK", _intensity(max(walk, back), th["walk_hz"]),
                        "back" if back > walk else "forward")
    return Behavior("NOTHING", 0.0)
