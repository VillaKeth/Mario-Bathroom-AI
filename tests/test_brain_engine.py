"""LIF engine on tiny synthetic networks: exact math, delay, inhibition,
refractory, Poisson rate, determinism, parallel == serial bit-for-bit."""
import math

import numpy as np

from server.brain import engine as E


def _csc(n, edges):
    """edges: [(pre, post, signed_synapses)] -> CSC sorted by (pre, post)."""
    edges = sorted(edges)
    indptr = np.zeros(n + 1, dtype=np.int64)
    for pre, _, _ in edges:
        indptr[pre + 1] += 1
    indptr = np.cumsum(indptr)
    indices = np.array([p for _, p, _ in edges], dtype=np.int32)
    data = np.array([w for _, _, w in edges], dtype=np.float32)
    return indptr, indices, data


def test_quiet_network_stays_silent():
    eng = E.Engine(*_csc(3, [(0, 1, 50), (1, 2, 50)]), gain=1.0)
    res = eng.run(50.0)
    assert res.n_spikes == 0 and res.n_active == 0


def test_single_event_matches_closed_form_after_exact_delay():
    eng = E.Engine(*_csc(2, [(0, 1, 10)]), gain=1.0)  # w = 2.75 mV, subthreshold
    ptr, idx = E.kicks_from_events(E.DELAY_STEPS, [(0, 0)])
    eng.run_kicks(E.DELAY_STEPS, ptr, idx)
    assert eng.v[1] == np.float32(E.V_REST_MV)  # nothing delivered before 1.8 ms
    k = 50
    eng.run_kicks(k, np.zeros(k + 1, np.int64), np.zeros(0, np.int32))
    w = 10 * E.W_SYN_MV
    t = k * E.DT_MS
    expect = w * E.TAU_S_MS / (E.TAU_S_MS - E.TAU_M_MS) * (
        math.exp(-t / E.TAU_S_MS) - math.exp(-t / E.TAU_M_MS))
    assert abs((float(eng.v[1]) - E.V_REST_MV) - expect) < 1e-3 * expect


def test_chain_fires_once_after_delay():
    eng = E.Engine(*_csc(2, [(0, 1, 200)]), gain=1.0)  # one spike is enough
    ptr, idx = E.kicks_from_events(E.DELAY_STEPS, [(0, 0)])
    first = eng.run_kicks(E.DELAY_STEPS, ptr, idx)
    assert first.counts.tolist() == [1, 0]
    later = eng.run_kicks(100, np.zeros(101, np.int64), np.zeros(0, np.int32))
    assert later.counts.tolist() == [0, 1]


def test_inhibition_blocks_firing():
    net = _csc(3, [(0, 2, 200), (1, 2, -400)])
    alone = E.Engine(*net, gain=1.0)
    ptr, idx = E.kicks_from_events(1, [(0, 0)])
    alone.run_kicks(1, ptr, idx)
    assert alone.run_kicks(100, np.zeros(101, np.int64), np.zeros(0, np.int32)).counts[2] == 1
    both = E.Engine(*net, gain=1.0)
    ptr, idx = E.kicks_from_events(1, [(0, 0), (0, 1)])
    both.run_kicks(1, ptr, idx)
    assert both.run_kicks(100, np.zeros(101, np.int64), np.zeros(0, np.int32)).counts[2] == 0


def test_refractory_caps_rate_exactly():
    eng = E.Engine(*_csc(1, []), gain=1.0)
    res = eng.run(230.0, np.array([0]), np.array([10_000.0]), seed=1)  # p = 1 per step
    assert int(res.counts[0]) == 100  # one spike per 23 steps (22 refractory + 1)


def test_poisson_rate_is_close_to_requested():
    # Kicks landing in the 2.2 ms refractory period are lost (dead time), so the
    # expected count is rate*T / (1 + rate*tau_ref) = 200 / 1.22 ~= 164.
    eng = E.Engine(*_csc(1, []), gain=1.0)
    res = eng.run(2000.0, np.array([0]), np.array([100.0]), seed=7)
    assert 135 <= int(res.counts[0]) <= 195


def test_same_seed_same_result():
    net = _csc(3, [(0, 1, 120), (1, 2, 120), (2, 0, 60)])
    a = E.Engine(*net, gain=1.0).run(100.0, np.array([0, 1]), np.array([150.0, 150.0]), seed=5)
    b = E.Engine(*net, gain=1.0).run(100.0, np.array([0, 1]), np.array([150.0, 150.0]), seed=5)
    assert a.counts.tolist() == b.counts.tolist()


def test_population_bins_count_spikes():
    pop_of = np.array([0, -1], dtype=np.int16)
    eng = E.Engine(*_csc(2, []), gain=1.0, pop_of=pop_of, n_pops=1)
    res = eng.run(230.0, np.array([0]), np.array([10_000.0]), seed=1, n_bins=10)
    assert res.pop_bins.shape == (1, 10)
    assert int(res.pop_bins.sum()) == 100 == res.n_spikes
    assert abs(res.bin_ms - 23.0) < 1e-9 and abs(res.sim_ms - 230.0) < 1e-9


def test_parallel_propagation_is_bit_identical_to_serial():
    rng = np.random.default_rng(0)
    n = 2000
    edges = []
    for pre in range(n):
        for post in rng.integers(0, n, size=30):
            w = int(rng.integers(1, 20)) * (-1 if rng.random() < 0.2 else 1)
            edges.append((pre, int(post), w))
    net = _csc(n, edges)
    stim = rng.choice(n, size=50, replace=False)
    hz = np.full(50, 300.0)
    serial = E.Engine(*net, gain=3.0, parts=1)
    par = E.Engine(*net, gain=3.0, parts=7, chunk=113, serial_edge_limit=0)
    rs = serial.run(50.0, stim, hz, seed=11)
    rp = par.run(50.0, stim, hz, seed=11)
    assert rs.n_spikes > 300  # every spiking step took the parallel propagation path in `par`
    assert rs.counts.tolist() == rp.counts.tolist()
    assert np.array_equal(serial.v, par.v) and np.array_equal(serial.g, par.g)


def test_split_windows_equal_one_window():
    """State (v, g, refractory, in-flight spikes) carries across windows exactly,
    whatever the window lengths (the kernel works in 18-step delay blocks)."""
    rng = np.random.default_rng(4)
    n = 300
    edges = [(pre, int(post), int(rng.integers(5, 60)) * (-1 if rng.random() < 0.25 else 1))
             for pre in range(n) for post in rng.integers(0, n, size=12)]
    net = _csc(n, edges)
    ptr, idx = E.poisson_kicks(np.arange(40), np.full(40, 400.0), 100, np.random.default_rng(9))
    one = E.Engine(*net, gain=1.0)
    whole = one.run_kicks(100, ptr, idx)
    two = E.Engine(*net, gain=1.0)
    cut = 37
    first = two.run_kicks(cut, ptr[:cut + 1], idx[:ptr[cut]])
    second = two.run_kicks(100 - cut, ptr[cut:] - ptr[cut], idx[ptr[cut]:])
    assert whole.n_spikes > 50
    assert (first.counts + second.counts).tolist() == whole.counts.tolist()
    assert np.array_equal(one.v, two.v) and np.array_equal(one.g, two.g)


def test_reset_returns_to_rest():
    eng = E.Engine(*_csc(2, [(0, 1, 10)]), gain=1.0)
    eng.run(20.0, np.array([0]), np.array([500.0]), seed=2)
    eng.reset()
    assert np.all(eng.v == np.float32(E.V_REST_MV)) and not eng.g.any()
