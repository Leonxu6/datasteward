"""Focused validation tests for FileConnector source directories."""

from pathlib import Path

import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector


def _connector(configured_dir) -> FileConnector:
    return FileConnector(
        Source(name="files", source_type="file", params={"dir": configured_dir})
    )


@pytest.mark.parametrize("configured_dir", [" /tmp/data", "/tmp/data ", "\t/tmp/data", "/tmp/data\n"])
def test_file_directory_rejects_padded_string_paths(configured_dir):
    connector = _connector(configured_dir)

    ok, message = connector.test_connection()

    assert ok is False
    assert "首尾空白" in message


def test_file_directory_accepts_path_objects(tmp_path: Path):
    ok, message = _connector(tmp_path).test_connection()

    assert ok is True
    assert message == "ok"


def test_file_directory_normalizes_invalid_pathlike_errors():
    class _BytesPath:
        def __fspath__(self):
            return b"/tmp/data"

    ok, message = _connector(_BytesPath()).test_connection()

    assert ok is False
    assert "不是有效路径" in message
