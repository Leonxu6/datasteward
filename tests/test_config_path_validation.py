from pathlib import Path

import pytest

from dm.config_validation import env_path


def test_env_path_expands_home_without_resolving(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("DM_PATH", "~/data/state.db")
    assert env_path("DM_PATH", "fallback") == str(tmp_path / "data" / "state.db")


def test_env_path_rejects_padding_controls_and_oversize(monkeypatch):
    for value in (" relative", "relative ", "bad\u200dpath"):
        monkeypatch.setenv("DM_PATH", value)
        with pytest.raises(ValueError):
            env_path("DM_PATH", "fallback")
    monkeypatch.setenv("DM_PATH", "x" * 4097)
    with pytest.raises(ValueError):
        env_path("DM_PATH", "fallback")


def test_env_path_validates_max_length_option(monkeypatch):
    monkeypatch.delenv("DM_PATH", raising=False)
    for limit in (0, -1, True, 1.5, "100", 4097):
        with pytest.raises(ValueError):
            env_path("DM_PATH", "fallback", max_length=limit)  # type: ignore[arg-type]


def test_env_path_normalizes_expanduser_failures(monkeypatch):
    monkeypatch.setenv("DM_PATH", "~/state.db")

    def fail_expanduser(_path):
        raise RuntimeError("backend detail")

    monkeypatch.setattr(Path, "expanduser", fail_expanduser)
    with pytest.raises(ValueError, match="路径无法展开") as caught:
        env_path("DM_PATH", "fallback")
    assert "backend detail" not in str(caught.value)
