"""MaleCNS v1.0 connectome: download the flat feathers, build the engine cache.

The raw data (~1.1 GB) lives outside every checkout, in
~/.cache/mario_ai/connectome/malecns_v1/. build_cache() turns it into one
net_v1.npz the engine loads in about a second.

Node policy (same as DOOMFLY): every body with an assigned superclass whose
status is not Glia -> 166,700 neurons. Edge policy: every edge between
retained nodes -> 25,582,938 connections, 124,177,617 synapses.
Sign: the first non-"unclear" of consensus_nt, celltype_predicted_nt,
predicted_nt; GABA, glutamate and histamine inhibit, everything else excites.

Data: MaleCNS v1.0, Janelia FlyEM et al., CC BY 4.0. This module preprocesses
it into a signed weight matrix (a change, as the licence requires us to say).
"""
import logging
import os
import urllib.request
from dataclasses import dataclass, fields

import numpy as np

logger = logging.getLogger(__name__)

BASE_URL = ("https://storage.googleapis.com/flyem-male-cns/v1.0/"
            "connectome-data/flat-connectome/")
FILES = {  # local name -> (remote name, exact size in bytes)
    "annotations.feather": ("body-annotations-male-cns-v1.0-minconf-0.5.feather", 14_483_314),
    "neurotransmitters.feather": ("body-neurotransmitters-male-cns-v1.0.feather", 43_282_834),
    "edges.feather": ("connectome-weights-male-cns-v1.0-minconf-0.5.feather", 1_051_241_946),
}
CACHE_NAME = "net_v1.npz"
CACHE_VERSION = 1
INHIBITORY = frozenset({"gaba", "glutamate", "histamine"})
ANN_COLS = ["bodyId", "superclass", "status", "type", "synonyms", "rootSide", "somaSide"]
NT_COLS = ["body", "consensus_nt", "celltype_predicted_nt", "predicted_nt"]


def default_dir():
    return os.path.join(os.path.expanduser("~"), ".cache", "mario_ai", "connectome", "malecns_v1")


def resolve_dir(d=None):
    return os.path.expanduser(d) if d else default_dir()


def cache_path(d):
    return os.path.join(d, CACHE_NAME)


def nt_sign(*candidates):
    """-1 for inhibitory transmitters, +1 otherwise; first non-'unclear' wins."""
    for c in candidates:
        if c and c != "unclear":
            return -1.0 if c in INHIBITORY else 1.0
    return 1.0


@dataclass
class Net:
    indptr: np.ndarray
    indices: np.ndarray
    data: np.ndarray
    body_ids: np.ndarray
    type_codes: np.ndarray
    type_vocab: np.ndarray
    superclass_codes: np.ndarray
    superclass_vocab: np.ndarray
    sides: np.ndarray
    syn_idx: np.ndarray
    syn_text: np.ndarray

    @property
    def n_neurons(self):
        return int(len(self.body_ids))

    @property
    def n_connections(self):
        return int(len(self.indices))

    @property
    def n_synapses(self):
        return int(np.abs(self.data).sum(dtype=np.float64))

    def type_of(self, i):
        return str(self.type_vocab[self.type_codes[i]])

    def superclass_of(self, i):
        return str(self.superclass_vocab[self.superclass_codes[i]])

    def synonyms_of(self, i):
        k = int(np.searchsorted(self.syn_idx, i))
        if k < len(self.syn_idx) and int(self.syn_idx[k]) == int(i):
            return str(self.syn_text[k])
        return ""


def save_net(net, path):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        np.savez(f, version=np.int32(CACHE_VERSION),
                 **{fl.name: getattr(net, fl.name) for fl in fields(Net)})
    os.replace(tmp, path)


def load_net(path):
    with np.load(path, allow_pickle=False) as z:
        if int(z["version"]) != CACHE_VERSION:
            raise ValueError(f"{path}: cache version {int(z['version'])}, need {CACHE_VERSION}")
        return Net(**{fl.name: z[fl.name] for fl in fields(Net)})


def _progress(cb, stage, frac):
    if cb is not None:
        cb(stage, frac)


def fetch(data_dir, files=None, progress=None, opener=None, chunk=1 << 20):
    """Download the raw feathers (resumable; exact-size checked)."""
    files = FILES if files is None else files
    opener = opener or urllib.request.urlopen
    os.makedirs(data_dir, exist_ok=True)
    total = float(sum(size for _, size in files.values())) or 1.0
    done = 0
    for local, (remote, size) in files.items():
        dst = os.path.join(data_dir, local)
        if os.path.isfile(dst) and os.path.getsize(dst) == size:
            done += size
            continue
        part = dst + ".part"
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        if have > size:
            os.remove(part)
            have = 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        req = urllib.request.Request(BASE_URL + remote, headers=headers)
        logger.info(f"[connectome] downloading {remote} ({size / 1e6:.0f} MB)")
        with opener(req, timeout=60) as resp, open(part, "ab" if have else "wb") as f:
            if have and getattr(resp, "status", 200) == 200:  # server ignored Range
                f.seek(0)
                f.truncate()
                have = 0
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                have += len(buf)
                _progress(progress, "fetch", (done + have) / total)
        if have != size:
            raise IOError(f"{local}: got {have} bytes, expected {size}")
        os.replace(part, dst)
        done += size


def _side(r):
    if r.get("rootSide") in ("L", "R"):
        return r["rootSide"]
    if r.get("somaSide") in ("L", "R", "M"):
        return r["somaSide"]
    return ""


def build_cache(data_dir, out_path=None, progress=None):
    """Raw feathers -> net_v1.npz. About 25 s and 4 GB RAM for MaleCNS."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.feather as pf

    out_path = out_path or cache_path(data_dir)
    _progress(progress, "build", 0.0)
    ann = pf.read_table(os.path.join(data_dir, "annotations.feather"), columns=ANN_COLS).to_pylist()
    keep = sorted((r for r in ann if r["superclass"] is not None and r["status"] != "Glia"),
                  key=lambda r: r["bodyId"])
    body_ids = np.array([r["bodyId"] for r in keep], dtype=np.int64)
    n = len(body_ids)
    type_vocab, type_codes = np.unique(np.array([r["type"] or "" for r in keep], dtype=str),
                                       return_inverse=True)
    sc_vocab, sc_codes = np.unique(np.array([r["superclass"] for r in keep], dtype=str),
                                   return_inverse=True)
    sides = np.array([_side(r) for r in keep], dtype="<U1")
    syn_idx = np.array([i for i, r in enumerate(keep) if r["synonyms"]], dtype=np.int32)
    syn_text = (np.array([keep[i]["synonyms"] for i in syn_idx], dtype=str)
                if len(syn_idx) else np.zeros(0, dtype="<U1"))
    _progress(progress, "build", 0.1)

    ids = pa.array(body_ids, pa.int64())
    nt = pf.read_table(os.path.join(data_dir, "neurotransmitters.feather"), columns=NT_COLS)
    nt = nt.filter(pc.is_in(nt["body"], value_set=ids)).to_pylist()
    sign = np.ones(n, dtype=np.float32)
    if nt:
        pos = np.searchsorted(body_ids, np.array([r["body"] for r in nt], dtype=np.int64))
        sign[pos] = [nt_sign(r["consensus_nt"], r["celltype_predicted_nt"], r["predicted_nt"])
                     for r in nt]
    _progress(progress, "build", 0.2)

    e = pf.read_table(os.path.join(data_dir, "edges.feather"),
                      columns=["body_pre", "body_post", "weight"])
    e = e.filter(pc.and_(pc.is_in(e["body_pre"], value_set=ids),
                         pc.is_in(e["body_post"], value_set=ids)))
    _progress(progress, "build", 0.6)
    pre = np.searchsorted(body_ids, e["body_pre"].to_numpy()).astype(np.int32)
    post = np.searchsorted(body_ids, e["body_post"].to_numpy()).astype(np.int32)
    w = e["weight"].to_numpy().astype(np.float32)
    del e
    order = np.lexsort((post, pre))
    pre, post, w = pre[order], post[order], w[order]
    indptr = np.zeros(n + 1, dtype=np.int64)
    indptr[1:] = np.cumsum(np.bincount(pre, minlength=n))
    data = (w * sign[pre]).astype(np.float32)
    _progress(progress, "build", 0.9)
    save_net(Net(indptr=indptr, indices=post, data=data, body_ids=body_ids,
                 type_codes=type_codes.astype(np.int32), type_vocab=type_vocab,
                 superclass_codes=sc_codes.astype(np.int32), superclass_vocab=sc_vocab,
                 sides=sides, syn_idx=syn_idx, syn_text=syn_text), out_path)
    _progress(progress, "build", 1.0)
    logger.info(f"[connectome] cache built: {n} neurons, {len(post)} connections -> {out_path}")
    return out_path


def _raw_present(d):
    return all(os.path.isfile(os.path.join(d, name)) for name in FILES)


def ensure(data_dir, auto_fetch=True, progress=None):
    """Load the cache, building (and if allowed, downloading) whatever is missing."""
    path = cache_path(data_dir)
    if not os.path.isfile(path):
        if not _raw_present(data_dir):
            if not auto_fetch:
                raise FileNotFoundError(
                    f"no connectome in {data_dir}; run: python scripts/fetch_connectome.py")
            fetch(data_dir, progress=progress)
        build_cache(data_dir, path, progress=progress)
    _progress(progress, "load", 0.0)
    return load_net(path)


def shuffle_targets(indptr, indices, data, seed=0):
    """Degree-preserving control: permute every edge's target, keep its weight and
    presynaptic neuron, re-sort each column (the engine binary-searches targets)."""
    rng = np.random.default_rng(seed)
    new = indices.copy()
    rng.shuffle(new)
    pre = np.repeat(np.arange(len(indptr) - 1, dtype=np.int32), np.diff(indptr))
    order = np.lexsort((new, pre))
    return indptr.copy(), new[order], data[order]
