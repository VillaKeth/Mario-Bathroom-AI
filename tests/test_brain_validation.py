"""The brain is real: literature pathways fire on MaleCNS at the configured gain,
and die when the wiring is shuffled. Needs ~/.cache/mario_ai/connectome/malecns_v1
(scripts/fetch_connectome.py); skipped otherwise."""
import os

import numpy as np
import pytest
import yaml

from server.brain import connectome, populations
from server.brain.worker import Brain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = connectome.cache_path(connectome.default_dir())
pytestmark = pytest.mark.skipif(not os.path.isfile(CACHE), reason="MaleCNS cache not built")


def _gain():
    with open(os.path.join(ROOT, "characters", "fly", "character.yaml"), encoding="utf-8") as f:
        return float((yaml.safe_load(f) or {}).get("brain", {}).get("gain", 0.5))


@pytest.fixture(scope="module")
def net():
    return connectome.load_net(CACHE)


@pytest.fixture(scope="module")
def brains(net):
    specs, noise = populations.load_spec()
    real = Brain(net, specs, noise, gain=_gain())
    ip, ind, dat = connectome.shuffle_targets(net.indptr, net.indices, net.data, seed=1)
    shuf_net = connectome.Net(**{**net.__dict__, "indptr": ip, "indices": ind, "data": dat})
    shuf = Brain(shuf_net, specs, noise, gain=_gain())
    return real, shuf


def _run(brain, stim, seed=1):
    brain.engine.reset()
    return brain.handle({"cmd": "run", "id": 1, "ms": 500, "seed": seed, "stim": stim})["rates"]


def test_sugar_drives_mn9_not_escape(brains):
    real, shuf = brains
    r = _run(real, [{"pop": "sugar", "rate": 150}])
    assert r["feed"] >= 80 and r["escape"] < 50
    assert _run(shuf, [{"pop": "sugar", "rate": 150}])["feed"] == 0


def test_looming_drives_giant_fiber(brains):
    real, shuf = brains
    assert _run(real, [{"pop": "loom", "rate": 150, "side": "R"}])["escape"] >= 50
    assert _run(shuf, [{"pop": "loom", "rate": 150, "side": "R"}])["escape"] == 0


def test_antenna_drives_grooming(brains):
    real, shuf = brains
    r = _run(real, [{"pop": "antenna", "rate": 150}])
    assert r["groom"] >= 30 and r["escape"] < 50
    assert _run(shuf, [{"pop": "antenna", "rate": 150}])["groom"] == 0


def test_bitter_suppresses_sugar_feeding(brains):
    real, _ = brains
    sugar = _run(real, [{"pop": "sugar", "rate": 150}])["feed"]
    mixed = _run(real, [{"pop": "sugar", "rate": 150}, {"pop": "bitter", "rate": 150}])["feed"]
    assert mixed <= 0.5 * sugar
