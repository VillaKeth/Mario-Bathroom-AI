from shared.character_loader import CharacterLoader


def _write(tmp_path, name, extra=""):
    d = tmp_path / name
    d.mkdir()
    (d / "character.yaml").write_text(
        f"identity:\n  name: {name}\n{extra}", encoding="utf-8")
    return CharacterLoader(str(tmp_path), name)


def test_model_absent_is_none(tmp_path):
    c = _write(tmp_path, "nobody")
    assert c.model is None


def test_model_read_from_yaml_top_level(tmp_path):
    c = _write(tmp_path, "jax", "model: llama3.2:3b\n")
    assert c.model == "llama3.2:3b"
