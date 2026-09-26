"""LIF engine on tiny synthetic networks: exact math, delay, inhibition,
Shiu's reset and refractoriness, Poisson rate, determinism, parallel == serial
bit-for-bit, and the block kernel == a plain per-step simulation of Shiu's model."""
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


def _random_net(n, fanout, seed, lo=5, hi=80):
    rng = np.random.default_rng(seed)
    return _csc(n, [(pre, int(post), int(rng.integers(lo, hi)) * (-1 if rng.random() < 0.25 else 1))
                    for pre in range(n) for post in rng.integers(0, n, size=fanout)])


def _reference(net, gain, n_steps, kick_ptr, kick_idx, targets):
    """Shiu et al. 2024 as Brian2 runs it (model.py: eq_rst 'v = v_rst; w = 0;
    g = 0 * mV', refractory='rfc', rfc = 2.2 ms, and rfc = 0 ms for every
    Poisson target), one plain step at a time in Brian2's schedule: integrate
    unless refractory, threshold, deliver synaptic input to g and Poisson kicks
    to v, reset the neurons that fired. Same float32 operations as the kernel."""
    indptr, indices, data = net
    n = len(indptr) - 1
    w = np.float32(E.W_SYN_MV * gain)
    u = np.zeros(n, np.float32)
    g = np.zeros(n, np.float32)
    last = np.full(n, -(10 ** 9), np.int64)
    rfc = np.full(n, E.REFRACTORY_STEPS, np.int64)
    rfc[np.asarray(targets, dtype=np.int64)] = 0
    ring = np.zeros((E.DELAY_STEPS, n), np.float32)
    counts = np.zeros(n, np.int64)
    for s in range(n_steps):
        free = (s - last) >= rfc  # Brian2: timestep(t - lastspike) >= timestep(rfc)
        un = np.where(free, u * E._A_M + g * E._C_GU, u)
        gn = np.where(free, g * E._A_S, g)
        fired = free & (un > E._U_TH)
        slot = s % E.DELAY_STEPS
        gn = gn + ring[slot]
        ring[slot] = 0
        gn[np.abs(gn) < E._EPS] = 0
        un[np.abs(un) < E._EPS] = 0
        un[fired] = 0
        gn[fired] = 0
        for k in range(kick_ptr[s], kick_ptr[s + 1]):
            if not fired[kick_idx[k]]:
                un[kick_idx[k]] += E._KICK
        last[fired] = s
        counts[fired] += 1
        for j in np.nonzero(fired)[0]:
            np.add.at(ring[slot], indices[indptr[j]:indptr[j + 1]], data[indptr[j]:indptr[j + 1]] * w)
        u, g = un, gn
    return counts, u, g


def test_block_kernel_matches_shiu_brian2_reference():
    net = _random_net(400, 20, seed=3)
    rng = np.random.default_rng(4)
    targets = rng.choice(400, size=40, replace=False)
    ptr, idx = E.poisson_kicks(targets, np.full(40, 300.0), 600, np.random.default_rng(5))
    ref_counts, ref_u, ref_g = _reference(net, 2.0, 600, ptr, idx, targets)
    assert ref_counts.sum() > 1000 and np.count_nonzero(ref_counts) > 100  # the network, not just the targets
    for kw in ({"parts": 1}, {"parts": 5, "chunk": 97, "serial_edge_limit": 0}):
        eng = E.Engine(*net, gain=2.0, **kw)
        res = eng.run_kicks(600, ptr, idx, targets=targets)
        assert res.counts.tolist() == ref_counts.tolist(), kw
        assert np.array_equal(eng.u, ref_u) and np.array_equal(eng.g, ref_g), kw


def test_dense_poisson_targets_fit_the_spike_buffers():
    # Poisson targets have no refractory period, so one can fire up to 9 times
    # in an 18-step block: 60 of them in one 97-neuron chunk at 3 kHz
    net = _random_net(300, 10, seed=6)
    targets = np.arange(60)
    ptr, idx = E.poisson_kicks(targets, np.full(60, 3000.0), 360, np.random.default_rng(1))
    ref_counts, _, _ = _reference(net, 1.0, 360, ptr, idx, targets)
    eng = E.Engine(*net, gain=1.0, parts=3, chunk=97, serial_edge_limit=0)
    res = eng.run_kicks(360, ptr, idx, targets=targets)
    assert ref_counts[:60].sum() > 60 * 360 // 18 * 3  # > 3 spikes per target per block
    assert res.counts.tolist() == ref_counts.tolist()


def test_spike_resets_synaptic_drive():
    # Shiu's reset is v = v_rst AND g = 0: one input volley, however large,
    # fires the target once instead of re-firing it on leftover drive
    eng = E.Engine(*_csc(2, [(0, 1, 2000)]), gain=1.0)  # 550 mV into g of neuron 1
    ptr, idx = E.kicks_from_events(1, [(0, 0)])
    eng.run_kicks(1, ptr, idx)
    later = eng.run_kicks(200, np.zeros(201, np.int64), np.zeros(0, np.int32))
    assert later.counts.tolist() == [1, 1]


def test_driven_neuron_refires_after_exactly_22_steps():
    # Brian2: not_refractory = timestep(t - lastspike) >= timestep(2.2 ms), so a
    # neuron flooded with input fires again 22 steps after its last spike
    pop_of = np.array([-1, 0], dtype=np.int16)
    eng = E.Engine(*_csc(2, [(0, 1, 10_000)]), gain=1.0, pop_of=pop_of, n_pops=1)
    ptr, idx = E.poisson_kicks(np.array([0]), np.array([10_000.0]), 400, np.random.default_rng(0))
    res = eng.run_kicks(400, ptr, idx, n_bins=400)
    steps = np.nonzero(res.pop_bins[0])[0]
    assert len(steps) > 10 and set(np.diff(steps).tolist()) == {22}


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
    # Brian2 order: the kick at step 0 lands after that step's threshold test, so
    # neuron 0 fires at step 1; its input lands in g at step 19 after that step's
    # integration, so neuron 1 has integrated for k - 2 steps
    t = (k - 2) * E.DT_MS
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


def test_poisson_target_has_no_refractory_period():
    # Shiu: neu[i].rfc = 0 * ms for every Poisson target. A kick lands after the
    # threshold test and one landing on a spike step is erased by the reset, so
    # a neuron kicked every step fires every other step.
    eng = E.Engine(*_csc(1, []), gain=1.0)
    res = eng.run(230.0, np.array([0]), np.array([10_000.0]), seed=1)  # p = 1 per step
    assert int(res.counts[0]) == 1150


def test_stimulated_neuron_fires_at_the_requested_rate():
    # spec 3.1: a stimulated neuron fires ~ at the requested rate; only kicks that
    # land on its own spike steps are lost (p = 1.5% at 150 Hz): ~295 in 2 s
    eng = E.Engine(*_csc(1, []), gain=1.0)
    res = eng.run(2000.0, np.array([0]), np.array([150.0]), seed=7)
    assert 265 <= int(res.counts[0]) <= 325


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
    assert int(res.pop_bins.sum()) == 1150 == res.n_spikes  # every other step, as above
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
    targets = np.arange(40)
    ptr, idx = E.poisson_kicks(targets, np.full(40, 400.0), 100, np.random.default_rng(9))
    one = E.Engine(*net, gain=1.0)
    whole = one.run_kicks(100, ptr, idx, targets=targets)
    two = E.Engine(*net, gain=1.0)
    cut = 37
    first = two.run_kicks(cut, ptr[:cut + 1], idx[:ptr[cut]], targets=targets)
    second = two.run_kicks(100 - cut, ptr[cut:] - ptr[cut], idx[ptr[cut]:], targets=targets)
    assert whole.n_spikes > 50
    assert (first.counts + second.counts).tolist() == whole.counts.tolist()
    assert np.array_equal(one.v, two.v) and np.array_equal(one.g, two.g)


def test_reset_returns_to_rest():
    eng = E.Engine(*_csc(2, [(0, 1, 10)]), gain=1.0)
    eng.run(20.0, np.array([0]), np.array([500.0]), seed=2)
    eng.reset()
    assert np.all(eng.v == np.float32(E.V_REST_MV)) and not eng.g.any()
