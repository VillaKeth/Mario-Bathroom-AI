"""Named neuron populations: sensory inputs the fly's senses drive, and motor or
descending readouts that decide its behavior. Resolved by cell type."""
import os
from dataclasses import dataclass

import numpy as np
import yaml

DEFAULT_SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "malecns_populations.yaml")


class PopulationError(ValueError):
    pass


@dataclass(frozen=True)
class PopSpec:
    name: str
    kind: str                 # "sense" | "readout"
    label: str
    types: tuple = ()
    prefixes: tuple = ()
    note: str = ""


def load_spec(path=DEFAULT_SPEC):
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    specs = []
    for name, d in (raw.get("populations") or {}).items():
        kind = d.get("kind")
        if kind not in ("sense", "readout"):
            raise PopulationError(f"population {name!r}: kind must be sense or readout")
        spec = PopSpec(name=str(name), kind=kind, label=str(d.get("label", str(name).upper())),
                       types=tuple(str(t) for t in d.get("types") or ()),
                       prefixes=tuple(str(p) for p in d.get("prefixes") or ()),
                       note=str(d.get("note", "")))
        if not spec.types and not spec.prefixes:
            raise PopulationError(f"population {name!r}: needs types or prefixes")
        specs.append(spec)
    return specs, tuple(raw.get("noise_superclasses") or ())


def resolve(net, specs):
    vocab = [str(t) for t in net.type_vocab]
    owner = np.full(net.n_neurons, -1, dtype=np.int32)
    out = {}
    for k, s in enumerate(specs):
        codes = [c for c, t in enumerate(vocab)
                 if t and (t in s.types or any(t.startswith(p) for p in s.prefixes))]
        idx = np.flatnonzero(np.isin(net.type_codes, codes)) if codes else np.zeros(0, np.int64)
        if len(idx) == 0:
            raise PopulationError(f"population {s.name!r} matched nothing "
                                  f"(types={s.types}, prefixes={s.prefixes})")
        taken = owner[idx]
        if (taken >= 0).any():
            other = specs[int(taken[taken >= 0][0])].name
            raise PopulationError(f"population {s.name!r} overlaps {other!r}")
        owner[idx] = k
        out[s.name] = idx.astype(np.int64)
    return out


def pop_of_array(pops, order, n):
    arr = np.full(n, -1, dtype=np.int16)
    for k, name in enumerate(order):
        arr[pops[name]] = k
    return arr


def side_filter(idx, sides, side):
    """Restrict to one side; if nothing is on that side, keep both."""
    if side not in ("L", "R", "M"):
        return idx
    sel = idx[sides[idx] == side]
    return sel if len(sel) else idx


def noise_pool(net, superclasses):
    wanted = set(superclasses)
    codes = [c for c, s in enumerate(net.superclass_vocab) if str(s) in wanted]
    return np.flatnonzero(np.isin(net.superclass_codes, codes)).astype(np.int64)
