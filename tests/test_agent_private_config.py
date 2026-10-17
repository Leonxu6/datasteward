import json
import os
import stat

import pytest

from dm.agent import core


def test_private_json_is_complete_and_owner_only(tmp_path):
    path = tmp_path / "mcp.json"
    value = {"identity": {"user": "operator", "purpose": "inventory review"}}

    core._write_private_json(path, value)

    assert json.loads(path.read_text(encoding="utf-8")) == value
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_private_json_refuses_to_replace_existing_content(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        core._write_private_json(path, {"new": True})

    assert path.read_text(encoding="utf-8") == "keep"


def test_private_json_removes_partial_file_when_write_fails(tmp_path, monkeypatch):
    path = tmp_path / "mcp.json"

    def fail_write(_descriptor, _payload):
        raise OSError("storage failure")

    monkeypatch.setattr(core.os, "write", fail_write)

    with pytest.raises(OSError, match="storage failure"):
        core._write_private_json(path, {"identity": "operator"})

    assert not path.exists()
