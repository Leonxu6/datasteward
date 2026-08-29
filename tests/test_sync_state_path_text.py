from pathlib import Path

import pytest

from dm.connect.sync_state import atomic_write_json, load_json_mapping


def test_state_paths_reject_padding_and_control_characters(tmp_path: Path):
    valid = tmp_path / "state.json"
    for bad in (f" {valid}", f"{valid} ", f"{valid}\n"):
        with pytest.raises(ValueError):
            load_json_mapping(bad)


def test_clean_state_path_still_round_trips(tmp_path: Path):
    path = tmp_path / "state.json"
    atomic_write_json(path, {"cursor": 7})
    assert load_json_mapping(path) == {"cursor": 7}
