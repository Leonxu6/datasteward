import pytest

from dm.docs import search as docs_search


def test_search_query_validation_rejects_ambiguous_or_unsafe_text():
    for value in (None, "", " padded", "padded ", "bad\x00query", "x" * 2001):
        with pytest.raises(ValueError):
            docs_search._query_text(value)


def test_search_query_validation_preserves_readable_multiline_queries():
    query = "S001 合同\n交付条件"
    assert docs_search._query_text(query) == query
