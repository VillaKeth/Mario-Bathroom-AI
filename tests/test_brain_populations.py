import numpy as np
import pytest

from server.brain import populations as P
from server.brain.connectome import Net


def _net(types, sides, superclasses):
    tv, tc = np.unique(np.array(types, dtype=str), return_inverse=True)
    sv, sc = np.unique(np.array(superclasses, dtype=str), return_inverse=True)
    n = len(types)
    return Net(indptr=np.zeros(n + 1, np.int64), indices=np.zeros(0, np.int32),
               data=np.zeros(0, np.float32), body_ids=np.arange(n, dtype=np.int64),
               type_codes=tc.astype(np.int32), type_vocab=tv, superclass_codes=sc.astype(np.int32),
               superclass_vocab=sv, sides=np.array(sides, dtype="<U1"),
               syn_idx=np.zeros(0, np.int32), syn_text=np.zeros(0, "<U1"))


def test_default_spec_loads_all_populations():
    specs, noise = P.load_spec()
    names = [s.name for s in specs]
    assert names == ["sugar", "bitter", "ears", "antenna", "loom",
                     "feed", "groom", "escape", "startle", "walk", "backup"]
    assert {s.kind for s in specs} == {"sense", "readout"}
    assert "cb_sensory" in noise


def test_resolve_exact_and_prefix_and_side_filter():
    net = _net(["LB3a", "LB3b", "JO-CA1", "JO-EV2", "MN9", "", "LB3a"],
               ["R", "L", "R", "L", "M", "", "L"],
               ["cb_sensory"] * 4 + ["cb_motor", "cb_intrinsic", "cb_sensory"])
    specs = [P.PopSpec("sugar", "sense", "SWEET", types=("LB3a", "LB3b")),
             P.PopSpec("antenna", "sense", "ANTENNA", prefixes=("JO-C", "JO-E")),
             P.PopSpec("feed", "readout", "FEED", types=("MN9",))]
    pops = P.resolve(net, specs)
    assert pops["sugar"].tolist() == [0, 1, 6]
    assert pops["antenna"].tolist() == [2, 3]
    assert P.side_filter(pops["sugar"], net.sides, "R").tolist() == [0]
    assert P.side_filter(pops["sugar"], net.sides, "both").tolist() == [0, 1, 6]
    # no neuron on the requested side -> fall back to both, never an empty stimulus
    assert P.side_filter(pops["antenna"], net.sides, "M").tolist() == [2, 3]
    of = P.pop_of_array(pops, ["sugar", "antenna", "feed"], net.n_neurons)
    assert of.tolist() == [0, 0, 1, 1, 2, -1, 0]
    assert P.noise_pool(net, ("cb_sensory",)).tolist() == [0, 1, 2, 3, 6]


def test_resolve_rejects_empty_and_overlapping():
    net = _net(["LB3a", "MN9"], ["R", "M"], ["cb_sensory", "cb_motor"])
    with pytest.raises(P.PopulationError, match="nothing"):
        P.resolve(net, [P.PopSpec("x", "sense", "X", types=("NOPE",))])
    with pytest.raises(P.PopulationError, match="overlaps"):
        P.resolve(net, [P.PopSpec("a", "sense", "A", types=("LB3a",)),
                        P.PopSpec("b", "sense", "B", prefixes=("LB",))])
