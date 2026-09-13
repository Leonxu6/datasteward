import pytest

from dm.config_validation import env_iso_date


def test_env_iso_date_accepts_canonical_date_and_empty_sentinel(monkeypatch):
    monkeypatch.setenv("DM_DATE", "2026-06-25")
    assert env_iso_date("DM_DATE") == "2026-06-25"
    monkeypatch.setenv("DM_DATE", "")
    assert env_iso_date("DM_DATE") == ""


def test_env_iso_date_rejects_invalid_or_noncanonical_values(monkeypatch):
    for value in (
        "2026-02-30",
        "2026-6-25",
        "25-06-2026",
        "2026/06/25",
        " 2026-06-25",
        "2026-06-25 ",
        "2026-06-25\u200d",
    ):
        monkeypatch.setenv("DM_DATE", value)
        with pytest.raises(ValueError):
            env_iso_date("DM_DATE")


def test_env_iso_date_can_require_a_value(monkeypatch):
    monkeypatch.delenv("DM_DATE", raising=False)
    with pytest.raises(ValueError):
        env_iso_date("DM_DATE", "", allow_empty=False)
