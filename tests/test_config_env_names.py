import pytest

from dm.config_validation import env_bool, env_float, env_int, env_text


def test_config_parsers_accept_shell_safe_environment_names(monkeypatch):
    monkeypatch.delenv("DM_VALUE_2", raising=False)
    assert env_text("DM_VALUE_2", "ok") == "ok"
    assert env_int("DM_VALUE_2", 2, minimum=0, maximum=10) == 2
    assert env_float("DM_VALUE_2", 0.5, minimum=0, maximum=1) == 0.5
    assert env_bool("DM_VALUE_2", False) is False


@pytest.mark.parametrize("name", [None, "", " DM_X", "DM_X ", "9DM_X", "DM-X", "DM.X", "变量"])
def test_config_parsers_reject_nonportable_environment_names(monkeypatch, name):
    monkeypatch.delenv("DM_X", raising=False)
    parsers = (
        lambda: env_text(name, "ok"),
        lambda: env_int(name, 1, minimum=0, maximum=10),
        lambda: env_float(name, 0.5, minimum=0, maximum=1),
        lambda: env_bool(name, False),
    )
    for parser in parsers:
        with pytest.raises(ValueError):
            parser()
