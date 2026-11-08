import os

import pytest

from dm.bounded_files import read_bounded_text


def test_read_bounded_text_rejects_final_symlink(tmp_path):
    target = tmp_path / "target.json"
    target.write_text('{"trusted": false}', encoding="utf-8")
    link = tmp_path / "manifest.json"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("symbolic links are not available on this platform")

    with pytest.raises((OSError, ValueError)):
        read_bounded_text(link, max_bytes=1024)


def test_read_bounded_text_rejects_path_swap_during_open(tmp_path, monkeypatch):
    original = tmp_path / "manifest.json"
    replacement = tmp_path / "replacement.json"
    original.write_text('{"version": 1}', encoding="utf-8")
    replacement.write_text('{"version": 2}', encoding="utf-8")
    real_open = os.open

    def swap_then_open(path, flags):
        original.replace(tmp_path / "old.json")
        replacement.replace(original)
        return real_open(path, flags)

    monkeypatch.setattr(os, "open", swap_then_open)
    with pytest.raises(ValueError, match="changed while it was being opened"):
        read_bounded_text(original, max_bytes=1024)
