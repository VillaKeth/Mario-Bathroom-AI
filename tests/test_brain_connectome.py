"""Connectome cache: node policy, NT sign precedence, edge filter, CSC layout, fetch."""
import io
import os

import numpy as np
import pyarrow as pa
import pyarrow.feather as pf
import pytest

from server.brain import connectome


def _write_raw(d):
    """Six bodies. 40 has no superclass; 50 is Glia -> both dropped."""
    pf.write_feather(pa.table({
        "bodyId": pa.array([30, 10, 20, 40, 50, 60], pa.int64()),
        "superclass": ["cb_sensory", "cb_intrinsic", "cb_motor", None, "cb_intrinsic", "descending_neuron"],
        "status": ["Traced", "Traced", "Traced", "Traced", "Glia", "Anchor"],
        "type": ["LB3a", "GNG1", "MN9", None, "GLIA", None],
        "synonyms": [None, "Shiu 2022: Rattle", None, None, None, None],
        "rootSide": ["R", None, None, None, None, None],
        "somaSide": [None, "L", "M", None, None, "R"],
    }), os.path.join(d, "annotations.feather"))
    pf.write_feather(pa.table({
        "body": pa.array([10, 20, 30, 60, 999], pa.int64()),
        "consensus_nt": ["unclear", "gaba", "unclear", "unclear", "gaba"],
        "celltype_predicted_nt": ["glutamate", "acetylcholine", "unclear", "unclear", "gaba"],
        "predicted_nt": ["acetylcholine", "acetylcholine", "unclear", "histamine", "gaba"],
    }), os.path.join(d, "neurotransmitters.feather"))
    pf.write_feather(pa.table({
        "body_pre": pa.array([30, 30, 10, 20, 40, 30, 60, 777], pa.int64()),
        "body_post": pa.array([20, 10, 30, 60, 10, 50, 20, 10], pa.int64()),
        "weight": pa.array([5, 3, 7, 2, 9, 4, 1, 8], pa.int64()),
    }), os.path.join(d, "edges.feather"))


def test_nt_sign_precedence():
    assert connectome.nt_sign("gaba", "acetylcholine", "acetylcholine") == -1.0
    assert connectome.nt_sign("unclear", "glutamate", "acetylcholine") == -1.0
    assert connectome.nt_sign("unclear", "unclear", "histamine") == -1.0
    assert connectome.nt_sign("unclear", "unclear", "dopamine") == 1.0
    assert connectome.nt_sign(None, "unclear", "unclear") == 1.0


def test_build_cache_node_policy_signs_and_csc(tmp_path):
    _write_raw(str(tmp_path))
    path = connectome.build_cache(str(tmp_path))
    net = connectome.load_net(path)
    # 40 (no superclass) and 50 (Glia) dropped; sorted by bodyId
    assert net.body_ids.tolist() == [10, 20, 30, 60]
    assert net.n_neurons == 4
    # edges touching 40, 50 or unknown 777 dropped
    pairs = []
    for j in range(net.n_neurons):
        for e in range(net.indptr[j], net.indptr[j + 1]):
            pairs.append((int(net.body_ids[j]), int(net.body_ids[net.indices[e]]), float(net.data[e])))
    # 10 glutamate (-1), 20 gaba (-1), 30 all unclear (+1), 60 histamine (-1)
    assert sorted(pairs) == [(10, 30, -7.0), (20, 60, -2.0), (30, 10, 3.0), (30, 20, 5.0), (60, 20, -1.0)]
    # targets sorted within each presynaptic column
    for j in range(net.n_neurons):
        col = net.indices[net.indptr[j]:net.indptr[j + 1]]
        assert np.all(np.diff(col) >= 0)
    assert net.n_connections == 5
    assert net.n_synapses == 18
    assert net.type_of(2) == "LB3a" and net.type_of(3) == ""
    assert net.superclass_of(1) == "cb_motor"
    assert net.sides.tolist() == ["L", "M", "R", "R"]  # rootSide wins over somaSide
    assert net.synonyms_of(0) == "Shiu 2022: Rattle" and net.synonyms_of(1) == ""


def test_ensure_builds_when_raw_present_and_refuses_without_fetch(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_connectome"):
        connectome.ensure(str(tmp_path), auto_fetch=False)
    _write_raw(str(tmp_path))
    net = connectome.ensure(str(tmp_path), auto_fetch=False)
    assert net.n_neurons == 4
    assert os.path.isfile(connectome.cache_path(str(tmp_path)))


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_fetch_downloads_skips_complete_and_checks_size(tmp_path):
    files = {"a.feather": ("remote_a", 5), "b.feather": ("remote_b", 3)}
    payload = {"remote_a": b"AAAAA", "remote_b": b"BBB"}
    calls = []

    def opener(req, timeout=60):
        name = req.full_url.rsplit("/", 1)[1]
        calls.append(name)
        return _Resp(payload[name])

    (tmp_path / "b.feather").write_bytes(b"BBB")  # already complete -> skipped
    connectome.fetch(str(tmp_path), files=files, opener=opener)
    assert (tmp_path / "a.feather").read_bytes() == b"AAAAA"
    assert calls == ["remote_a"]

    bad = {"c.feather": ("remote_a", 99)}
    with pytest.raises(IOError, match="expected 99"):
        connectome.fetch(str(tmp_path), files=bad, opener=opener)


def test_shuffle_targets_keeps_degrees_and_sorted_columns():
    indptr = np.array([0, 3, 5, 6], dtype=np.int64)
    indices = np.array([0, 1, 2, 0, 2, 1], dtype=np.int32)
    data = np.array([1, 2, 3, 4, 5, 6], dtype=np.float32)
    ip, ind, dat = connectome.shuffle_targets(indptr, indices, data, seed=3)
    assert ip.tolist() == indptr.tolist()
    assert sorted(ind.tolist()) == sorted(indices.tolist())
    for j in range(3):
        col = ind[ip[j]:ip[j + 1]]
        assert np.all(np.diff(col) >= 0)
        assert sorted(dat[ip[j]:ip[j + 1]].tolist()) == sorted(data[indptr[j]:indptr[j + 1]].tolist())
