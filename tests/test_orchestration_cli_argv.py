import sys

import pytest

from dm.orchestration.cli_argv import temporary_argv


def test_temporary_argv_restores_the_existing_list_contents():
    original_object = sys.argv
    original_values = list(sys.argv)

    with temporary_argv(["dm-docs", "build"]):
        assert sys.argv == ["dm-docs", "build"]
        assert sys.argv is original_object

    assert sys.argv is original_object
    assert sys.argv == original_values


def test_temporary_argv_restores_state_after_exceptions():
    original = list(sys.argv)
    with pytest.raises(RuntimeError, match="boom"):
        with temporary_argv(["dm-kg", "build"]):
            raise RuntimeError("boom")
    assert sys.argv == original


def test_temporary_argv_rejects_invalid_arguments_before_mutation():
    original = list(sys.argv)
    with pytest.raises(ValueError, match="invalid argument"):
        with temporary_argv(["dm-docs", "bad\x00arg"]):
            pass
    assert sys.argv == original
