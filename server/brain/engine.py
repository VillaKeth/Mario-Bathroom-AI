"""Leaky integrate-and-fire engine for a whole connectome.

Parameters follow Shiu et al. 2024 (Nature 634:210), plus one global gain on
the synaptic weight (spec section 3.2: MaleCNS at Shiu's weight is
supercritical; gain 0.5 is the lowest tested value at which sugar->MN9,
looming->giant fiber and JO-C/E->aDN all fire while shuffled wiring is silent).

State per neuron, in mV: membrane u = v - v_rest and synaptic drive g.
    du/dt = (g - u) / tau_m        dg/dt = -g / tau_s
The system is linear, so each 0.1 ms step is the exact update
    u <- u*a_m + g*c               g <- g*a_s
During the refractory period nothing integrates, but arriving input still
accumulates in g (Brian2 "unless refractory" semantics, as in Shiu's code).
A spike from neuron j adds data[e] * w to g of each target 18 steps later,
through an 18-slot ring buffer; only neurons that spiked propagate.

Delay blocks: a spike needs 18 steps to arrive, so no spike fired inside an
18-step block can reach any neuron before the block ends. The kernel
therefore integrates a whole block per neuron range without synchronizing,
then propagates the block's spikes into the ring. That is exactly the
step-by-step result with 18x fewer thread barriers, and each thread keeps its
slice of the state in cache for the whole block.

Parallelism: integration is split over neuron chunks; propagation over
TARGET ranges -- each thread binary-searches every spiker's target-sorted
out-edges down to its own range, so no two threads write the same target and
every target sums its inputs in spiker order. Results are therefore
bit-identical for any thread count.
"""
import time
from dataclasses import dataclass

import numpy as np
from numba import get_num_threads, njit, prange

DT_MS = 0.1
TAU_M_MS = 20.0
TAU_S_MS = 5.0
V_REST_MV = -52.0
V_RESET_MV = -52.0
V_THRESH_MV = -45.0
REFRACTORY_STEPS = 22          # 2.2 ms
DELAY_STEPS = 18               # 1.8 ms
W_SYN_MV = 0.275               # Shiu 2024, per synapse, before gain
POISSON_KICK_MV = 250 * W_SYN_MV

_A_M = np.float32(np.exp(-DT_MS / TAU_M_MS))
_A_S = np.float32(np.exp(-DT_MS / TAU_S_MS))
_C_GU = np.float32(TAU_S_MS / (TAU_S_MS - TAU_M_MS)
                   * (np.exp(-DT_MS / TAU_S_MS) - np.exp(-DT_MS / TAU_M_MS)))
_U_RESET = np.float32(V_RESET_MV - V_REST_MV)
_U_TH = np.float32(V_THRESH_MV - V_REST_MV)
_KICK = np.float32(POISSON_KICK_MV)
_EPS = np.float32(1e-6)
_ZERO = np.float32(0.0)
_REFR = np.int32(REFRACTORY_STEPS)
_I0 = np.int32(0)
_I1 = np.int32(1)


@njit(cache=True)
def _integrate(u, g, refr, row):
    """One step for a contiguous slice of neurons. Branch-free and indexed from 0,
    so LLVM vectorizes it: an offset index (range(lo, hi)) keeps numba's
    negative-index wraparound check, which blocks SIMD and costs ~4x."""
    for i in range(u.shape[0]):
        gi = g[i] + row[i]
        row[i] = _ZERO
        r = refr[i]
        ui = u[i]
        un = ui * _A_M + gi * _C_GU
        gn = gi * _A_S
        ref = r > _I0
        sp = (not ref) and (un > _U_TH)
        gn = _ZERO if (gn > -_EPS and gn < _EPS) else gn
        un = _ZERO if (un > -_EPS and un < _EPS) else un
        u[i] = ui if ref else (_U_RESET if sp else un)
        g[i] = gi if ref else gn
        refr[i] = (r - _I1) if ref else (_REFR if sp else _I0)


@njit(cache=True)
def _collect(refr, lo, out, m):
    """Append lo+i for every neuron in the slice that fired this step (only a
    neuron that fired this step holds the full refractory count)."""
    for i in range(refr.shape[0]):
        if refr[i] == _REFR:
            out[m] = lo + i
            m += 1
    return m


@njit(parallel=True, cache=True)
def _run_kernel(indptr, indices, data, w, u, g, refr, ring, step0, n_steps,
                kick_ptr, kick_idx, pop_of, pop_bins, bin_spikes, bin_steps,
                counts, chunk, cnt, coff, spk_buf, spk_list, step_ptr,
                part_bounds, serial_edge_limit):
    n = u.shape[0]
    n_chunks = cnt.shape[0]
    n_parts = part_bounds.shape[0] - 1
    delay = ring.shape[0]
    total = 0
    for b0 in range(0, n_steps, delay):
        blk = min(delay, n_steps - b0)
        # A. integrate the whole block, parallel over neuron chunks. A neuron
        #    fires at most once per block (refractory 22 steps > block of 18).
        for c in prange(n_chunks):
            lo = c * chunk
            hi = min(n, lo + chunk)
            uu = u[lo:hi]
            gg = g[lo:hi]
            rr = refr[lo:hi]
            m = 0
            for j in range(blk):
                s = b0 + j
                # Poisson kicks for this step that land in this chunk (sorted)
                ka = kick_ptr[s]
                kb = kick_ptr[s + 1]
                if ka < kb:
                    k = ka + np.searchsorted(kick_idx[ka:kb], lo)
                    while k < kb and kick_idx[k] < hi:
                        i = kick_idx[k] - lo
                        if rr[i] == 0:
                            uu[i] += _KICK
                        k += 1
                _integrate(uu, gg, rr, ring[(step0 + s) % delay][lo:hi])
                m0 = m
                m = _collect(rr, lo, spk_buf[lo:hi], m)
                cnt[c, j] = m - m0
        # B. gather the block's spikes in (step, neuron) order; count and bin
        for c in range(n_chunks):
            coff[c] = 0
        ns = 0
        blk_edges = 0
        for j in range(blk):
            step_ptr[j] = ns
            b = (b0 + j) // bin_steps
            for c in range(n_chunks):
                base = c * chunk + coff[c]
                for k in range(cnt[c, j]):
                    i = spk_buf[base + k]
                    spk_list[ns] = i
                    ns += 1
                    counts[i] += 1
                    p = pop_of[i]
                    if p >= 0:
                        pop_bins[p, b] += 1
                    blk_edges += indptr[i + 1] - indptr[i]
                coff[c] += cnt[c, j]
            bin_spikes[b] += ns - step_ptr[j]
        step_ptr[blk] = ns
        total += ns
        if ns == 0:
            continue
        # C. propagate each step's spikes into that step's slot = delivery
        #    DELAY steps later (the slot was consumed during block A)
        if n_parts <= 1 or blk_edges <= serial_edge_limit:
            for j in range(blk):
                row = ring[(step0 + b0 + j) % delay]
                for k in range(step_ptr[j], step_ptr[j + 1]):
                    src = spk_list[k]
                    for e in range(indptr[src], indptr[src + 1]):
                        row[indices[e]] += data[e] * w
        else:
            for q in prange(n_parts):
                t_lo = part_bounds[q]
                t_hi = part_bounds[q + 1]
                for j in range(blk):
                    row = ring[(step0 + b0 + j) % delay]
                    for k in range(step_ptr[j], step_ptr[j + 1]):
                        src = spk_list[k]
                        a = indptr[src]
                        e_end = indptr[src + 1]
                        if a == e_end:
                            continue
                        e = a + np.searchsorted(indices[a:e_end], t_lo)
                        while e < e_end:
                            t = indices[e]
                            if t >= t_hi:
                                break
                            row[t] += data[e] * w
                            e += 1
    return total


def _balanced_bounds(indices, n, parts):
    """Split targets 0..n into `parts` ranges holding ~equal in-degree."""
    if parts <= 1 or n == 0:
        return np.array([0, n], dtype=np.int32)
    cum = np.cumsum(np.bincount(indices, minlength=n).astype(np.int64))
    cuts = np.searchsorted(cum, np.linspace(0, cum[-1], parts + 1)[1:-1], side="left") + 1
    bounds = np.concatenate([[0], np.clip(cuts, 0, n), [n]])
    return np.maximum.accumulate(bounds).astype(np.int32)


def poisson_kicks(stim_idx, stim_hz, n_steps, rng):
    """Independent Poisson trains -> CSR by step (kick_ptr[n_steps+1], kick_idx),
    neurons ascending within each step."""
    if stim_idx is None or len(stim_idx) == 0:
        return np.zeros(n_steps + 1, dtype=np.int64), np.zeros(0, dtype=np.int32)
    idx = np.asarray(stim_idx, dtype=np.int32)
    p = np.clip(np.asarray(stim_hz, dtype=np.float64) * (DT_MS / 1000.0), 0.0, 1.0)
    steps, who = [], []
    block = max(1, 4_000_000 // len(idx))
    for s0 in range(0, n_steps, block):
        s1 = min(n_steps, s0 + block)
        st, col = np.nonzero(rng.random((s1 - s0, len(idx))) < p)
        steps.append(st + s0)
        who.append(idx[col])
    steps = np.concatenate(steps)
    who = np.concatenate(who).astype(np.int32)
    order = np.lexsort((who, steps))
    kick_ptr = np.zeros(n_steps + 1, dtype=np.int64)
    np.add.at(kick_ptr, steps + 1, 1)
    return np.cumsum(kick_ptr), who[order]


def kicks_from_events(n_steps, events):
    """Explicit kicks [(step, neuron), ...] (tests, warm-up)."""
    ev = sorted(events)
    kick_ptr = np.zeros(n_steps + 1, dtype=np.int64)
    for s, _ in ev:
        kick_ptr[s + 1] += 1
    return np.cumsum(kick_ptr), np.array([i for _, i in ev], dtype=np.int32)


@dataclass
class WindowResult:
    counts: np.ndarray
    pop_bins: np.ndarray
    bin_spikes: np.ndarray
    bin_ms: float
    sim_ms: float
    wall_ms: float

    @property
    def n_spikes(self):
        return int(self.bin_spikes.sum())

    @property
    def n_active(self):
        return int(np.count_nonzero(self.counts))


class Engine:
    def __init__(self, indptr, indices, data, gain=0.5, pop_of=None, n_pops=0,
                 parts=None, chunk=None, serial_edge_limit=20_000):
        self.indptr = np.ascontiguousarray(indptr, dtype=np.int64)
        self.indices = np.ascontiguousarray(indices, dtype=np.int32)
        self.data = np.ascontiguousarray(data, dtype=np.float32)
        self.n = len(self.indptr) - 1
        self.gain = float(gain)
        self.w = np.float32(W_SYN_MV * self.gain)
        self.pop_of = (np.full(self.n, -1, dtype=np.int16) if pop_of is None
                       else np.ascontiguousarray(pop_of, dtype=np.int16))
        self.n_pops = int(n_pops)
        threads = max(1, get_num_threads())
        self.parts = int(parts) if parts else threads
        self.chunk = int(chunk) if chunk else max(1024, -(-self.n // (threads * 4)))
        self.serial_edge_limit = int(serial_edge_limit)  # per 18-step block
        self.part_bounds = _balanced_bounds(self.indices, self.n, self.parts)
        n_chunks = max(1, -(-self.n // self.chunk))
        self._cnt = np.zeros((n_chunks, DELAY_STEPS), dtype=np.int64)
        self._coff = np.zeros(n_chunks, dtype=np.int64)
        self._step_ptr = np.zeros(DELAY_STEPS + 1, dtype=np.int64)
        self._spk_buf = np.zeros(max(1, self.n), dtype=np.int32)
        self._spk_list = np.zeros(max(1, self.n), dtype=np.int32)
        self.reset()

    @property
    def v(self):
        """Membrane potential in mV (the kernel stores u = v - v_rest)."""
        return self.u + np.float32(V_REST_MV)

    def reset(self):
        self.u = np.zeros(self.n, dtype=np.float32)
        self.g = np.zeros(self.n, dtype=np.float32)
        self.refr = np.zeros(self.n, dtype=np.int32)
        self.ring = np.zeros((DELAY_STEPS, self.n), dtype=np.float32)
        self.step = 0

    def run(self, ms, stim_idx=None, stim_hz=None, seed=0, n_bins=10):
        n_steps = max(1, int(round(float(ms) / DT_MS)))
        ptr, idx = poisson_kicks(stim_idx, stim_hz, n_steps, np.random.default_rng(seed))
        return self.run_kicks(n_steps, ptr, idx, n_bins=n_bins)

    def run_kicks(self, n_steps, kick_ptr, kick_idx, n_bins=10):
        """kick_idx must be ascending within each step (poisson_kicks and
        kicks_from_events guarantee it)."""
        n_bins = max(1, min(int(n_bins), n_steps))
        bin_steps = -(-n_steps // n_bins)
        n_bins = -(-n_steps // bin_steps)
        counts = np.zeros(self.n, dtype=np.int32)
        pop_bins = np.zeros((max(1, self.n_pops), n_bins), dtype=np.int32)
        bin_spikes = np.zeros(n_bins, dtype=np.int64)
        t0 = time.perf_counter()
        _run_kernel(self.indptr, self.indices, self.data, self.w, self.u, self.g,
                    self.refr, self.ring, self.step, n_steps,
                    np.ascontiguousarray(kick_ptr, dtype=np.int64),
                    np.ascontiguousarray(kick_idx, dtype=np.int32),
                    self.pop_of, pop_bins, bin_spikes, bin_steps, counts, self.chunk,
                    self._cnt, self._coff, self._spk_buf, self._spk_list, self._step_ptr,
                    self.part_bounds, self.serial_edge_limit)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        self.step += n_steps
        return WindowResult(counts=counts, pop_bins=pop_bins[:self.n_pops],
                            bin_spikes=bin_spikes, bin_ms=bin_steps * DT_MS,
                            sim_ms=n_steps * DT_MS, wall_ms=wall_ms)
