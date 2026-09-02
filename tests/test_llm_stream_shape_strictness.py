import pytest

from dm.llm import _stream_content


def test_stream_rejects_falsey_non_list_choices():
    for choices in (None, "", {}, 0):
        with pytest.raises(RuntimeError, match="choices"):
            _stream_content({"choices": choices})


def test_stream_rejects_falsey_non_mapping_delta():
    for delta in (None, "", [], 0):
        with pytest.raises(RuntimeError, match="delta"):
            _stream_content({"choices": [{"delta": delta}]})


def test_stream_allows_explicit_empty_choices_and_delta_mapping():
    assert _stream_content({"choices": []}) is None
    assert _stream_content({"choices": [{"delta": {}}]}) is None
