import json
import os
import subprocess
import sys

import numpy as np

from server.brain import connectome, populations
from server.brain.connectome import Net
from server.brain.worker import Brain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tiny_net():
    """0,1 = sugar (R,L); 2 = feed. Strong 0->2 and 1->2 edges; 3 is a noise sensory neuron."""
    types = np.array(["LB3a", "LB3a", "MN9", "JO-CA1"], dtype=str)
    tv, tc = np.unique(types, return_inverse=True)
    sv, sc = np.unique(np.array(["cb_sensory", "cb_sensory", "cb_motor", "cb_sensory"], dtype=str),
                       return_inverse=True)
    return Net(indptr=np.array([0, 1, 2, 2, 2], np.int64), indices=np.array([2, 2], np.int32),
               data=np.array([400.0, 400.0], np.float32), body_ids=np.arange(4, dtype=np.int64),
               type_codes=tc.astype(np.int32), type_vocab=tv, superclass_codes=sc.astype(np.int32),
               superclass_vocab=sv, sides=np.array(["R", "L", "M", "R"], dtype="<U1"),
               syn_idx=np.zeros(0, np.int32), syn_text=np.zeros(0, "<U1"))


def _specs():
    return [populations.PopSpec("sugar", "sense", "SWEET", types=("LB3a",)),
            populations.PopSpec("antenna", "sense", "ANTENNA", prefixes=("JO-C",)),
            populations.PopSpec("feed", "readout", "FEED", types=("MN9",))]


def test_brain_run_drives_readout_and_reports_rates():
    b = Brain(_tiny_net(), _specs(), ("cb_sensory",), gain=1.0)
    b.warm_up()
    r = b.handle({"cmd": "run", "id": 4, "ms": 200, "seed": 1,
                  "stim": [{"pop": "sugar", "rate": 150, "side": "both"}]})
    assert r["status"] == "ok" and r["id"] == 4
    assert r["rates"]["sugar"] > 50 and r["rates"]["feed"] > 20  # ~113 Hz after dead time
    assert len(r["bins"]["feed"]) == 10 and r["spikes"] > 0 and r["sim_ms"] == 200.0


def test_brain_side_and_bad_requests():
    b = Brain(_tiny_net(), _specs(), ("cb_sensory",), gain=1.0)
    r = b.handle({"cmd": "run", "id": 1, "ms": 100, "stim": [{"pop": "sugar", "rate": 200, "side": "R"}]})
    assert r["rates"]["sugar"] > 0  # only neuron 0 driven: half the population
    bad = b.handle({"cmd": "run", "id": 2, "stim": [{"pop": "feed", "rate": 100}]})
    assert bad["status"] == "error" and "not a sense population" in bad["error"]
    assert b.handle({"cmd": "ping", "id": 3})["status"] == "pong"
    assert b.handle({"cmd": "bogus", "id": 5})["status"] == "error"


def test_brain_noise_only_window():
    b = Brain(_tiny_net(), _specs(), ("cb_sensory",), gain=1.0)
    r = b.handle({"cmd": "run", "id": 1, "ms": 200, "seed": 3, "stim": [],
                  "noise": {"frac": 1.0, "rate": 200}})
    assert r["status"] == "ok" and r["spikes"] > 0


def test_ready_payload_shape():
    b = Brain(_tiny_net(), _specs(), ("cb_sensory",), gain=1.0)
    p = b.ready_payload()
    assert p["status"] == "ready" and p["neurons"] == 4 and p["connections"] == 2
    assert p["order"] == ["sugar", "antenna", "feed"]
    assert p["populations"]["feed"] == {"size": 1, "label": "FEED", "kind": "readout"}


def test_worker_subprocess_protocol(tmp_path):
    cache = str(tmp_path / "net.npz")
    connectome.save_net(_tiny_net(), cache)
    spec = tmp_path / "pops.yaml"
    spec.write_text("populations:\n"
                    "  sugar: {kind: sense, label: SWEET, types: [LB3a]}\n"
                    "  feed: {kind: readout, label: FEED, types: [MN9]}\n"
                    "noise_superclasses: [cb_sensory]\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "server.brain.worker", "--cache", cache,
                             "--populations", str(spec), "--gain", "1.0"],
                            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    try:
        lines = []
        while True:
            msg = json.loads(proc.stdout.readline())
            lines.append(msg)
            if msg["status"] != "loading":
                break
        assert lines[-1]["status"] == "ready", lines
        proc.stdin.write(json.dumps({"cmd": "run", "id": 9, "ms": 100, "seed": 2,
                                     "stim": [{"pop": "sugar", "rate": 150}]}) + "\n")
        proc.stdin.flush()
        reply = json.loads(proc.stdout.readline())
        assert reply["id"] == 9 and reply["status"] == "ok" and "feed" in reply["rates"]
        proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
        proc.stdin.flush()
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
