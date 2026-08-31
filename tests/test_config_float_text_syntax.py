import pytest

from dm.config_validation import env_float


@pytest.mark.parametrize("value", ["1_000.0", "+1.5", "１２.５"])
def test_float_settings_reject_noncanonical_numeric_spellings(monkeypatch, value):
    monkeypatch.setenv("DM_TEST_FLOAT", value)
    with pytest.raises(ValueError, match="必须是数字"):
        env_float("DM_TEST_FLOAT", 1.0, minimum=-10_000, maximum=10_000)


def test_float_settings_keep_ascii_scientific_notation(monkeypatch):
    monkeypatch.setenv("DM_TEST_FLOAT", "-1.25e+2")
    assert env_float("DM_TEST_FLOAT", 1.0, minimum=-1000, maximum=1000) == -125.0
