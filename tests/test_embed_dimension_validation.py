from pathlib import Path
from unittest.mock import patch

import pytest

from dm.docs.embed import _cache_dir, _clean_setting_text, _dimension


def test_embedding_dimension_accepts_bounded_ascii_integers():
    assert _dimension(1) == 1
    assert _dimension("512") == 512
    assert _dimension(8192) == 8192


@pytest.mark.parametrize("value", [0, -1, 8193, True, 1.5, None, "", " 512", "512 ", "+512", "５１２"])
def test_embedding_dimension_rejects_ambiguous_or_out_of_range_values(value):
    with pytest.raises(ValueError):
        _dimension(value)


def test_embedding_setting_text_rejects_padding_controls_and_oversize_values():
    assert _clean_setting_text("BAAI/model", field="model", max_length=20) == "BAAI/model"
    for value in (None, "", " model", "model ", "bad\nname", "bad\u200dname", "bad\ud800name", "x" * 21):
        with pytest.raises(ValueError):
            _clean_setting_text(value, field="model", max_length=20)
    for limit in (0, -1, True, 1.5, "10"):
        with pytest.raises(ValueError):
            _clean_setting_text("model", field="model", max_length=limit)


def test_embedding_cache_directory_expands_home_and_defaults(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/embed-home")
    assert _cache_dir("~/models") == "/tmp/embed-home/models"
    assert _cache_dir(None) == "/tmp/embed-home/.cache/dm_fastembed"
    assert _cache_dir("") == "/tmp/embed-home/.cache/dm_fastembed"


def test_embedding_cache_directory_normalizes_expansion_failures():
    with patch.object(Path, "expanduser", side_effect=RuntimeError("home unavailable")):
        with pytest.raises(ValueError, match="could not be expanded"):
            _cache_dir("~/models")
