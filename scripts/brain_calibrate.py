"""Re-derive every number the fly brain is tuned on; write a JSON report.

    python scripts/brain_calibrate.py [--gain G] [--sweep] [--out PATH]
        [--sections validation,bitter,senses,idle,timing,carry]

validation  literature pathways at --gain, real vs target-shuffled wiring (seeds 1-3)
bitter      sugar vs sugar+bitter MN9 (3 seeds) - the inferred bitter group
senses      canonical party lines -> stimulus -> brain -> behavior
idle        noise frac x rate grid -> behavior histogram (sets brain.noise)
timing      wall ms per 500 ms window (quiet, sugar, antenna, bitter; median of 3)
carry       spikes in quiet windows that follow a driven one without a reset
            (why brain.persist is false)
--sweep     also the gain table of spec section 3.2 (seeds 1-3, real and shuffled,
            sugar+bitter, carry)
"""
import argparse
import collections
import json
import os
import random
import statistics
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import yaml  # noqa: E402

from server.brain import connectome, populations  # noqa: E402
from server.brain.worker import Brain  # noqa: E402

VALIDATION = [
    ("sugar -> feed", [{"pop": "sugar", "rate": 150}], "feed"),
    ("loom R -> escape", [{"pop": "loom", "rate": 150, "side": "R"}], "escape"),
    ("antenna -> groom", [{"pop": "antenna", "rate": 150}], "groom"),
]
SUGAR_BITTER = [{"pop": "sugar", "rate": 150}, {"pop": "bitter", "rate": 150}]
SEEDS = (1, 2, 3)
SWEEP_GAINS = (0.4, 0.5, 0.55, 0.6, 0.62, 0.63, 0.65, 0.7, 0.8, 1.0)
SENSE_LINES = ["hello there", "HEY WHAT IS UP!!", "have some candy", "cake and beer and candy",
               "you're so cute", "you are disgusting", "ew gross you stupid bug",
               "I'm gonna swat you", "get the fly swatter", "blow on it", "so much dust in here"]
# A window over this many spikes has recruited the network at large (at gain 0.65:
# antenna drive ~110k, bitter ~490k, self-sustaining carried-over state ~590k);
# a quiet one stays in the hundreds.
BUSY_SPIKES = 100_000


def _fly_cfg():
    with open(os.path.join(ROOT, "characters", "fly", "character.yaml"), encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("brain", {})


def _window(brain, stim, seed=1, noise=None, reset=True):
    if reset:
        brain.engine.reset()
    r = brain.handle({"cmd": "run", "id": 0, "ms": 500, "seed": seed, "stim": stim,
                      "noise": noise or {}})
    return r


def _shuffled_net(net):
    ip, ind, dat = connectome.shuffle_targets(net.indptr, net.indices, net.data, seed=1)
    return connectome.Net(**{**net.__dict__, "indptr": ip, "indices": ind, "data": dat})


def _carry(brain, n=3):
    """Spikes in n quiet windows (no input, no noise) after an antenna-driven window,
    without a reset in between: what a persisting fly would carry."""
    _window(brain, [{"pop": "antenna", "rate": 150}], seed=1)
    return [_window(brain, [], seed=10 + k, reset=False)["spikes"] for k in range(n)]


def _hz(xs):
    return "/".join(f"{x:.1f}" for x in xs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gain", type=float, default=None)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "characters", "fly", "brain", "calibration.json"))
    ap.add_argument("--sections", default="validation,bitter,senses,idle,timing,carry")
    args = ap.parse_args()
    sections = set(args.sections.split(","))
    cfg = _fly_cfg()
    gain = args.gain if args.gain is not None else float(cfg.get("gain", 0.65))
    net = connectome.ensure(connectome.resolve_dir(cfg.get("cache_dir")), auto_fetch=False)
    specs, noise_sc = populations.load_spec()
    brain = Brain(net, specs, noise_sc, gain=gain)
    brain.warm_up()
    shuf_net = _shuffled_net(net) if ("validation" in sections or args.sweep) else None
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "dataset": "MaleCNS v1.0",
              "credit": "MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0; LIF after Shiu et al. 2024",
              "neurons": net.n_neurons, "connections": net.n_connections, "synapses": net.n_synapses,
              "gain": gain, "seeds": list(SEEDS), "populations": {n: int(len(i)) for n, i in brain.pops.items()}}

    if "validation" in sections:
        shuf = Brain(shuf_net, specs, noise_sc, gain=gain)
        rows = []
        for label, stim, target in VALIDATION:
            real_r = [_window(brain, stim, seed=s)["rates"] for s in SEEDS]
            shuf_hz = [_window(shuf, stim, seed=s)["rates"][target] for s in SEEDS]
            rows.append({"case": label, "target": target, "real_hz": [r[target] for r in real_r],
                         "shuffled_hz": shuf_hz, "real_all_seed1": real_r[0]})
            print(f"{label:20s} real {_hz(r[target] for r in real_r)} Hz   shuffled {_hz(shuf_hz)} Hz")
        report["validation"] = rows

    if "bitter" in sections:
        alone = [_window(brain, [{"pop": "sugar", "rate": 150}], seed=s)["rates"]["feed"] for s in SEEDS]
        mixed = [_window(brain, SUGAR_BITTER, seed=s)["rates"]["feed"] for s in SEEDS]
        report["bitter"] = {"sugar_alone_feed_hz": alone, "sugar_plus_bitter_feed_hz": mixed,
                            "note": "bitter = LB1a-e, inferred via Shiu's co-activation test"}
        print("bitter", _hz(alone), "->", _hz(mixed))

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
            w = _window(brain, stim)
            r = w["rates"]
            b = classify(r, th, stim={s["pop"]: s["rate"] for s in stim})
            rows.append({"text": line, "stim": stim, "behavior": b.name, "intensity": b.intensity,
                         "spikes": w["spikes"], "rates": r})
            print(f"{line:28s} -> {b.name:8s} {b.intensity:.2f}  spikes {w['spikes']}")
        report["senses"] = rows

    if "idle" in sections:
        persist = bool(cfg.get("persist", False))
        report["persist"] = persist
        rows = []
        for frac in (0.001, 0.002, 0.005, 0.01, 0.02, 0.05):
            for rate in (5.0, 10.0, 20.0):
                brain.engine.reset()
                hist = collections.Counter()
                spikes = []
                for k in range(20):  # as at the party: each window from rest unless brain.persist
                    r = _window(brain, [], seed=100 + k, noise={"frac": frac, "rate": rate},
                                reset=not persist)
                    hist[classify(r["rates"], th, stim={}).name] += 1
                    spikes.append(r["spikes"])
                busy = sum(s > BUSY_SPIKES for s in spikes)
                rows.append({"frac": frac, "rate": rate, "behaviors": dict(hist), "busy": busy,
                             "spikes_median": statistics.median(spikes), "spikes_max": max(spikes)})
                print(f"noise frac {frac:.3f} rate {rate:4.0f}: {dict(hist)}  busy {busy}/20  "
                      f"spikes median {statistics.median(spikes):.0f} max {max(spikes)}")
        report["idle"] = rows

    if "timing" in sections:
        timing = {}
        for name, stim in (("quiet", []), ("sugar", [{"pop": "sugar", "rate": 150}]),
                           ("antenna", [{"pop": "antenna", "rate": 150}]),
                           ("bitter", [{"pop": "bitter", "rate": 150}])):
            ws = [_window(brain, stim, seed=s) for s in SEEDS]
            timing[name] = {"wall_ms_median": statistics.median(w["wall_ms"] for w in ws),
                            "wall_ms_max": max(w["wall_ms"] for w in ws),
                            "spikes_median": statistics.median(w["spikes"] for w in ws)}
            print(f"timing {name:8s} wall median {timing[name]['wall_ms_median']:.0f} ms "
                  f"max {timing[name]['wall_ms_max']:.0f} ms  spikes {timing[name]['spikes_median']:.0f}")
        report["timing"] = timing

    if "carry" in sections:
        carry = _carry(brain)
        report["carry"] = {"drive": "antenna 150 Hz, then quiet windows without reset",
                           "quiet_window_spikes": carry}
        print("carry after antenna:", carry)

    if args.sweep:
        rows = []
        for g in SWEEP_GAINS:
            b = Brain(net, specs, noise_sc, gain=g)
            sb = Brain(shuf_net, specs, noise_sc, gain=g)
            row = {"gain": g}
            for label, stim, target in VALIDATION:
                ws = [_window(b, stim, seed=s) for s in SEEDS]
                row[label] = [w["rates"][target] for w in ws]
                row[label + " (shuffled)"] = [_window(sb, stim, seed=s)["rates"][target] for s in SEEDS]
                if target == "feed":
                    row["sugar_spikes"] = [w["spikes"] for w in ws]
            row["sugar+bitter -> feed"] = [_window(b, SUGAR_BITTER, seed=s)["rates"]["feed"] for s in SEEDS]
            row["carry_spikes"] = _carry(b)
            rows.append(row)
            print(f"gain {g}: " + "  ".join(f"{k} {_hz(v)}" for k, v in row.items()
                                           if k not in ("gain", "sugar_spikes", "carry_spikes"))
                  + f"  sugar spikes {row['sugar_spikes']}  carry {row['carry_spikes']}", flush=True)
        report["gain_sweep"] = rows

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
