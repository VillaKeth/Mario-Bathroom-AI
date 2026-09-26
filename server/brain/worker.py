"""Brain subprocess: owns the connectome + engine, speaks JSON lines on stdio.

    python -m server.brain.worker [--dir D | --cache NPZ] [--populations YAML]
                                  [--gain 0.65] [--threads 0] [--no-fetch]

stdout carries protocol lines only; every log line goes to stderr.
Protocol: docs/superpowers/specs/2026-09-25-fly-brain-design.md section 3.6.
"""
import argparse
import json
import sys

import numpy as np

from . import connectome, populations
from .engine import Engine


class Brain:
    """Everything the worker does except the stdio loop (so tests can drive it)."""

    def __init__(self, net, specs, noise_superclasses=(), gain=0.65, engine_kwargs=None):
        self.net = net
        self.specs = {s.name: s for s in specs}
        self.order = [s.name for s in specs]
        self.pops = populations.resolve(net, specs)
        self.gain = float(gain)
        self.engine = Engine(net.indptr, net.indices, net.data, gain=self.gain,
                             pop_of=populations.pop_of_array(self.pops, self.order, net.n_neurons),
                             n_pops=len(self.order), **(engine_kwargs or {}))
        self.noise_pool = populations.noise_pool(net, noise_superclasses)

    def warm_up(self):
        """Compile the kernel now, not on the first guest."""
        self.engine.run(1.0, np.array([0]), np.array([100.0]), seed=0)
        self.engine.reset()

    def ready_payload(self, dataset="malecns_v1"):
        return {
            "status": "ready", "dataset": dataset,
            "neurons": self.net.n_neurons, "connections": self.net.n_connections,
            "synapses": self.net.n_synapses, "gain": self.gain, "order": list(self.order),
            "populations": {n: {"size": int(len(self.pops[n])), "label": self.specs[n].label,
                                "kind": self.specs[n].kind} for n in self.order},
        }

    def handle(self, req):
        cmd, rid = req.get("cmd"), req.get("id")
        if cmd == "ping":
            return {"status": "pong", "id": rid}
        if cmd == "reset":
            self.engine.reset()
            return {"status": "ok", "id": rid}
        if cmd == "run":
            try:
                return {"status": "ok", "id": rid, **self._run(req)}
            except Exception as e:  # a bad request must never kill the worker
                return {"status": "error", "id": rid, "error": f"{type(e).__name__}: {e}"}
        return {"status": "error", "id": rid, "error": f"unknown cmd {cmd!r}"}

    def _run(self, req):
        ms = min(max(float(req.get("ms", 500)), 1.0), 5000.0)
        seed = int(req.get("seed", 0)) & 0x7FFFFFFF
        rng = np.random.default_rng(seed)
        idx_parts, hz_parts = [], []
        for s in req.get("stim") or []:
            name = s.get("pop")
            spec = self.specs.get(name)
            if spec is None or spec.kind != "sense":
                raise ValueError(f"not a sense population: {name!r}")
            idx = populations.side_filter(self.pops[name], self.net.sides, s.get("side", "both"))
            idx_parts.append(idx)
            hz_parts.append(np.full(len(idx), min(max(float(s.get("rate", 0.0)), 0.0), 1000.0)))
        noise = req.get("noise") or {}
        frac = float(noise.get("frac") or 0.0)
        nrate = min(max(float(noise.get("rate") or 0.0), 0.0), 1000.0)
        if frac > 0 and nrate > 0 and len(self.noise_pool):
            k = min(len(self.noise_pool), max(1, int(round(frac * len(self.noise_pool)))))
            pick = rng.choice(self.noise_pool, size=k, replace=False)
            idx_parts.append(pick)
            hz_parts.append(np.full(k, nrate))
        stim_idx = np.concatenate(idx_parts) if idx_parts else np.zeros(0, np.int64)
        stim_hz = np.concatenate(hz_parts) if hz_parts else np.zeros(0)
        if req.get("reset"):
            self.engine.reset()  # start this window from rest (a trial, as in Shiu 2024)
        return self.summarize(self.engine.run(ms, stim_idx, stim_hz, seed=seed))

    def summarize(self, res):
        sim_s, bin_s = res.sim_ms / 1000.0, res.bin_ms / 1000.0
        rates, bins = {}, {}
        for k, name in enumerate(self.order):
            size = len(self.pops[name])
            pb = res.pop_bins[k]
            rates[name] = round(float(pb.sum()) / (size * sim_s), 2)
            bins[name] = [round(float(x) / (size * bin_s), 1) for x in pb]
        return {"rates": rates, "bins": bins, "spikes": res.n_spikes, "active": res.n_active,
                "sim_ms": round(res.sim_ms, 1), "wall_ms": round(res.wall_ms, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="fly brain worker")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--populations", default=populations.DEFAULT_SPEC)
    ap.add_argument("--gain", type=float, default=0.65)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args(argv)

    proto = sys.stdout
    sys.stdout = sys.stderr  # stray prints must never corrupt the protocol

    def emit(obj):
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    def progress(stage, frac):
        emit({"status": "loading", "stage": stage, "progress": round(float(frac), 3)})

    try:
        if args.threads > 0:
            import numba
            numba.set_num_threads(min(args.threads, numba.config.NUMBA_NUM_THREADS))
        if args.cache:
            progress("load", 0.0)
            net = connectome.load_net(args.cache)
        else:
            net = connectome.ensure(connectome.resolve_dir(args.dir),
                                    auto_fetch=not args.no_fetch, progress=progress)
        specs, noise_sc = populations.load_spec(args.populations)
        progress("jit", 0.0)
        brain = Brain(net, specs, noise_sc, gain=args.gain)
        brain.warm_up()
    except Exception as e:
        emit({"status": "error", "fatal": True, "error": f"{type(e).__name__}: {e}"})
        return 1
    emit(brain.ready_payload())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            emit({"status": "error", "error": "bad json"})
            continue
        if req.get("cmd") == "quit":
            break
        emit(brain.handle(req))
    return 0


if __name__ == "__main__":
    sys.exit(main())
