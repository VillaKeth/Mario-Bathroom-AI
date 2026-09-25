"""The fly: party events in, whatever the fly's neurons do out.

senses -> one brain window in the worker -> behavior -> words -> voice.
No persona anywhere: the only choices here are how events reach the senses
(senses.yaml) and which words exist (words.yaml).

Each window starts from rest unless brain.persist is set: MaleCNS at gain 0.5
is supercritical in sustained operation, so carried-over state ends up in a
self-sustaining whole-brain ignition that never decays.
"""
import asyncio
import os
import random
import sys
import time
from dataclasses import dataclass, field

from .behavior import DEFAULT_THRESHOLDS, Behavior, classify
from .client import BrainClient
from .senses import SenseMapper
from .voice import FlyVoice
from .words import FlyWords

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDIT = ("Connectome: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0 · "
          "LIF after Shiu et al. 2024 · bitter taste group inferred")
IDLE_SPEAKS = frozenset({"FEED", "WALK"})  # spec 4.5


@dataclass
class FlyReply:
    text: str
    audio: bytes
    behavior: Behavior
    panel: dict = field(default_factory=dict)

    @property
    def emotion(self):
        return self.behavior.emotion

    @property
    def pose_hint(self):
        return self.behavior.pose


def worker_command(cfg):
    cmd = [sys.executable, "-m", "server.brain.worker",
           "--gain", str(float(cfg.get("gain", 0.5))),
           "--threads", str(int(cfg.get("threads", 0) or 0))]
    if cfg.get("cache_dir"):
        cmd += ["--dir", os.path.expanduser(str(cfg["cache_dir"]))]
    if not cfg.get("auto_fetch", True):
        cmd.append("--no-fetch")
    return cmd


class FlyBrain:
    def __init__(self, character_dir, cfg, edge_fn, llm_fn=None, client=None, rng=None):
        self.cfg = dict(cfg or {})
        self._rng = rng or random.Random()
        bdir = os.path.join(character_dir, "brain")
        self.senses = SenseMapper.from_yaml(os.path.join(bdir, "senses.yaml"), rng=self._rng)
        wcfg = self.cfg.get("words") or {}
        self.words = FlyWords.from_yaml(os.path.join(bdir, "words.yaml"),
                                        llm_fn=llm_fn if wcfg.get("llm", True) else None,
                                        max_words=int(wcfg.get("max_words", 6)),
                                        timeout_s=float(wcfg.get("timeout_s", 3.0)), rng=self._rng)
        vcfg = self.cfg.get("voice") or {}
        self.voice = FlyVoice(edge_fn, carrier_hz=float(vcfg.get("carrier_hz", 200.0)),
                              mix=float(vcfg.get("mix", 0.55)), bed=float(vcfg.get("bed", 0.06)))
        self.voice_timeout_s = float(vcfg.get("timeout_s", 8.0))
        self.thresholds = {**DEFAULT_THRESHOLDS, **(self.cfg.get("behavior") or {})}
        self.window_ms = int(self.cfg.get("window_ms", 500))
        self.persist = bool(self.cfg.get("persist", False))
        ncfg = self.cfg.get("noise") or {}
        # calibrated: denser noise ignites the whole brain from rest (calibration.json idle)
        self.noise = {"frac": float(ncfg.get("frac", 0.002)), "rate": float(ncfg.get("rate", 5.0))}
        self.client = client or BrainClient(worker_command(self.cfg), cwd=PROJECT_ROOT)
        self.last = None

    @property
    def status(self):
        return self.client.status

    async def start(self):
        await self.client.start()

    async def stop(self):
        await self.client.stop()

    async def react_text(self, text):
        return await self._react(self.senses.from_text(text), None, True, "text")

    async def react_event(self, event):
        return await self._react(self.senses.from_event(event), None, True, event)

    async def idle(self):
        return await self._react([], self.noise, False, "idle")

    async def _speak(self, text):
        """Edge + ring mod off the loop; a hung Edge (captive portal) becomes a buzz."""
        try:
            return await asyncio.wait_for(asyncio.to_thread(self.voice.speak, text),
                                          self.voice_timeout_s)
        except asyncio.TimeoutError:
            return self.voice.buzz(0.5)

    async def _react(self, stim, noise, use_llm, source):
        seed = self._rng.randrange(1 << 31)
        window = await self.client.run([s.to_dict() for s in stim], ms=self.window_ms,
                                       seed=seed, noise=noise, reset=not self.persist)
        rates = (window or {}).get("rates") or {}
        tasted = {s.pop: s.rate for s in stim}
        behavior = classify(rates, self.thresholds, stim=tasted) if window else Behavior("NOTHING")
        text = await self.words.speak(behavior, rates, use_llm=use_llm) if window else ""
        if source == "idle" and behavior.name not in IDLE_SPEAKS:
            text = ""  # spec 4.5: idle GROOM/REJECT are pose + panel only
        audio = b""
        if behavior.name == "ESCAPE":
            audio = self.voice.buzz(behavior.intensity)
        elif text:
            audio = await self._speak(text)
        self.last = {"time": time.time(), "source": source, "stim": [s.to_dict() for s in stim],
                     "behavior": behavior.name, "direction": behavior.direction,
                     "intensity": behavior.intensity, "text": text, "window": window}
        return FlyReply(text=text, audio=audio, behavior=behavior,
                        panel=self.panel(window, behavior, stim, source))

    def panel(self, window=None, behavior=None, stim=(), source=""):
        info = self.client.info or {}
        pops = info.get("populations") or {}
        order = info.get("order") or list(pops)
        behavior = behavior or Behavior("NOTHING")
        w = window or {}
        return {
            "status": self.client.status, "stage": self.client.stage,
            "progress": round(float(self.client.progress or 0.0), 3),
            "dataset": {"name": "MaleCNS v1.0", "neurons": info.get("neurons"),
                        "connections": info.get("connections"), "synapses": info.get("synapses")},
            "rows": [{"pop": p, "label": pops[p].get("label", p), "kind": pops[p].get("kind", "")}
                     for p in order if p in pops],
            "rates": w.get("rates") or {}, "bins": w.get("bins") or {},
            "spikes": w.get("spikes", 0), "active": w.get("active", 0),
            "sim_ms": w.get("sim_ms", 0), "wall_ms": w.get("wall_ms", 0),
            "behavior": behavior.name, "direction": behavior.direction,
            "pose_hint": behavior.pose, "emotion": behavior.emotion,
            "stim": [s.to_dict() for s in stim], "source": source, "credit": CREDIT,
        }

    def snapshot(self):
        return {"status": self.client.status, "stage": self.client.stage,
                "progress": self.client.progress, "error": self.client.error,
                "info": self.client.info, "last": self.last}
