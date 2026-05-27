from shared.character_errors import CharacterNotFoundError, CharacterConfigError

def test_not_found_lists_available():
    err = CharacterNotFoundError("sonic", "/chars", ["mario", "luigi"])
    assert "sonic" in str(err)
    assert "mario, luigi" in str(err)

def test_not_found_empty_available():
    err = CharacterNotFoundError("sonic", "/chars", [])
    assert "none" in str(err)

def test_config_error_with_name():
    err = CharacterConfigError("missing identity.name", character_name="mario")
    assert "mario" in str(err)
    assert "missing identity.name" in str(err)

def test_config_error_without_name():
    err = CharacterConfigError("invalid YAML syntax")
    assert "invalid YAML syntax" in str(err)
