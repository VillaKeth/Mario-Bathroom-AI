from server.group_config import GroupConfig


def _write(tmp_path, text):
    p = tmp_path / "tadc.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_loads_roster_and_models(tmp_path):
    path = _write(tmp_path, """
name: tadc
shared_model: llama3.1:8b
director_model: llama3.2:3b
roster:
  - id: pomni
  - id: jax
    model: qwen2.5:3b
""")
    g = GroupConfig.load(path)
    assert g.name == "tadc"
    assert g.shared_model == "llama3.1:8b"
    assert g.director_model == "llama3.2:3b"
    assert g.member_ids == ["pomni", "jax"]


def test_model_resolution_shared_vs_override(tmp_path):
    path = _write(tmp_path, """
name: tadc
shared_model: llama3.1:8b
director_model: llama3.2:3b
roster:
  - id: pomni
  - id: jax
    model: qwen2.5:3b
""")
    g = GroupConfig.load(path)
    assert g.model_for("pomni") == "llama3.1:8b"   # shared (no override)
    assert g.model_for("jax") == "qwen2.5:3b"      # override
    assert sorted(g.distinct_models()) == ["llama3.1:8b", "qwen2.5:3b"]


def test_director_model_defaults_to_shared_when_absent(tmp_path):
    path = _write(tmp_path, "name: t\nshared_model: m1\nroster:\n  - id: a\n")
    g = GroupConfig.load(path)
    assert g.director_model == "m1"
