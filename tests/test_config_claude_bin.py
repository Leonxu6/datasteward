import os

import pytest

from dm import config


def test_resolve_claude_accepts_explicit_executable(monkeypatch, tmp_path):
    executable = tmp_path / "claude"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("CLAUDE_BIN", str(executable))

    assert config.resolve_claude() == str(executable)


def test_resolve_claude_rejects_padded_or_overlong_override(monkeypatch):
    for value in (" /tmp/claude", "/tmp/claude ", "x" * 4097):
        monkeypatch.setenv("CLAUDE_BIN", value)
        with pytest.raises(ValueError):
            config.resolve_claude()


def test_resolve_claude_rejects_hidden_control_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "claude\u200d")
    with pytest.raises(ValueError, match="控制字符"):
        config.resolve_claude()
