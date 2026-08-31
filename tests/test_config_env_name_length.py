import pytest

from dm.config_validation import env_text


def test_environment_variable_names_have_a_bounded_length(monkeypatch):
    name = "A" * 128
    monkeypatch.setenv(name, "ok")
    assert env_text(name, "fallback") == "ok"

    with pytest.raises(ValueError, match="128"):
        env_text("A" * 129, "fallback")
