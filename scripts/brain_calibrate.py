"""Re-derive every number the fly brain is tuned on; write a JSON report.

    python scripts/brain_calibrate.py [--gain G] [--sweep] [--out PATH]
        [--sections validation,bitter,senses,idle,timing]

validation  literature pathways at --gain, real vs target-shuffled wiring
bitter      sugar vs sugar+bitter MN9 (3 seeds) - the inferred bitter group
senses      canonical party lines -> stimulus -> brain -> behavior
idle        noise frac x rate grid -> behavior histogram (sets brain.noise)
timing      wall ms per 500 ms window (quiet, sugar)
--sweep     also the gain table of spec section 3.2
"""
import argparse
import collections
import json
import os
import random
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from server.brain import connectome, populations  # noqa: E402
from server.brain.worker import Brain  # noqa: E402

VALIDATION = [
    ("sugar -> feed", [{"pop": "sugar", "rate": 150}], "feed"),
    ("loom R -> escape", [{"pop": "loom", "rate": 150, "side": "R"}], "escape"),
    ("antenna -> groom", [{"pop": "antenna", "rate": 150}], "groom"),
]
SENSE_LINES = ["hello there", "HEY WHAT IS UP!!", "have some candy", "cake and beer and candy",
               "you're so cute", "you are disgusting", "ew gross you stupid bug",
               "I'm gonna swat you", "get the fly swatter", "blow on it", "so much dust in here"]


def _fly_cfg():
    with open(os.path.join(ROOT, "characters", "fly", "character.yaml"), encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("brain", {})


def _window(brain, stim, seed=1, noise=None, reset=True):
    if reset:
        brain.engine.reset()
    r = brain.handle({"cmd": "run", "id": 0, "ms": 500, "seed": seed, "stim": stim,
                      "noise": noise or {}})
    return r


def _shuffled(net, specs, noise, gain):
    ip, ind, dat = connectome.shuffle_targets(net.indptr, net.indices, net.data, seed=1)
    return Brain(connectome.Net(**{**net.__dict__, "indptr": ip, "indices": ind, "data": dat}),
                 specs, noise, gain=gain)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gain", type=float, default=None)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "characters", "fly", "brain", "calibration.json"))
    ap.add_argument("--sections", default="validation,bitter,senses,idle,timing")
    args = ap.parse_args()
    sections = set(args.sections.split(","))
    cfg = _fly_cfg()
    gain = args.gain if args.gain is not None else float(cfg.get("gain", 0.5))
    net = connectome.ensure(connectome.resolve_dir(cfg.get("cache_dir")), auto_fetch=False)
    specs, noise_sc = populations.load_spec()
    brain = Brain(net, specs, noise_sc, gain=gain)
    brain.warm_up()
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "dataset": "MaleCNS v1.0",
              "credit": "MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0; LIF after Shiu et al. 2024",
              "neurons": net.n_neurons, "connections": net.n_connections, "synapses": net.n_synapses,
              "gain": gain, "populations": {n: int(len(i)) for n, i in brain.pops.items()}}

    if "validation" in sections:
        shuf = _shuffled(net, specs, noise_sc, gain)
        rows = []
        for label, stim, target in VALIDATION:
            real_r = _window(brain, stim)["rates"]
            shuf_r = _window(shuf, stim)["rates"]
            rows.append({"case": label, "target": target, "real_hz": real_r[target],
                         "shuffled_hz": shuf_r[target], "real_all": real_r})
            print(f"{label:20s} real {real_r[target]:7.1f} Hz   shuffled {shuf_r[target]:7.1f} Hz")
        report["validation"] = rows

    if "bitter" in sections:
        alone = [_window(brain, [{"pop": "sugar", "rate": 150}], seed=s)["rates"]["feed"] for s in (1, 2, 3)]
        mixed = [_window(brain, [{"pop": "sugar", "rate": 150}, {"pop": "bitter", "rate": 150}], seed=s)["rates"]["feed"]
                 for s in (1, 2, 3)]
        report["bitter"] = {"sugar_alone_feed_hz": alone, "sugar_plus_bitter_feed_hz": mixed,
                            "note": "bitter = LB1a-e, inferred via Shiu's co-activation test"}
        print("bitter", alone, "->", mixed)

    if "senses" in sections or "idle" in sections:
        from server.brain.behavior import DEFAULT_THRESHOLDS, classify
        from server.brain.senses import SenseMapper
        th = {**DEFAULT_THRESHOLDS, **(cfg.get("behavior") or {})}
    if "senses" in sections:
        mapper = SenseMapper.from_yaml(os.path.join(ROOT, "characters", "fly", "brain", "senses.yaml"),
                                       rng=random.Random(0))
        rows = []
        for line in SENSE_LINES:
            stim = [s.to_dict() for s in mapper.from_text(line)]
            r = _window(brain, stim)["rates"]
            b = classify(r, th)
            rows.append({"text": line, "stim": stim, "behavior": b.name, "intensity": b.intensity,
                         "rates": r})
            print(f"{line:28s} -> {b.name:8s} {b.intensity:.2f}")
        report["senses"] = rows

    if "idle" in sections:
        rows = []
        for frac in (0.01, 0.02, 0.05):
            for rate in (5.0, 10.0, 20.0):
                brain.engine.reset()
                hist = collections.Counter()
                for k in range(20):  # sequential windows, state persists, as at the party
                    r = _window(brain, [], seed=100 + k, noise={"frac": frac, "rate": rate}, reset=False)
                    hist[classify(r["rates"], th).name] += 1
                rows.append({"frac": frac, "rate": rate, "behaviors": dict(hist)})
                print(f"noise frac {frac:.2f} rate {rate:4.0f}: {dict(hist)}")
        report["idle"] = rows

    if "timing" in sections:
        quiet = _window(brain, [])["wall_ms"]
        busy = _window(brain, [{"pop": "sugar", "rate": 150}])["wall_ms"]
        report["timing"] = {"quiet_wall_ms": quiet, "sugar_wall_ms": busy}
        print(f"timing: quiet {quiet:.0f} ms, sugar {busy:.0f} ms per 500 ms window")

    if args.sweep:
        rows = []
        for g in (0.25, 0.35, 0.42, 0.5, 0.6):
            b = Brain(net, specs, noise_sc, gain=g)
            row = {"gain": g}
            for label, stim, target in VALIDATION:
                row[label] = _window(b, stim)["rates"][target]
            rows.append(row)
            print(row)
        report["gain_sweep"] = rows

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
