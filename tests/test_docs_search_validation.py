import pytest

from dm.docs import search as docs_search


def test_search_query_validation_rejects_ambiguous_or_unsafe_text():
    for value in (None, "", " padded", "padded ", "bad\x00query", "x" * 2001):
        with pytest.raises(ValueError):
            docs_search._query_text(value)


def test_search_query_validation_preserves_readable_multiline_queries():
    query = "S001 合同\n交付条件"
    assert docs_search._query_text(query) == query


def test_search_top_k_validation_rejects_bool_non_integer_and_out_of_range_values():
    for value in (True, 1.5, "5", 0, -1, 101):
        with pytest.raises(ValueError):
            docs_search._top_k(value)
    assert docs_search._top_k(1) == 1
    assert docs_search._top_k(100) == 100


def test_query_vector_requires_non_empty_finite_numeric_1d_data():
    for value in ([], [[1.0, 2.0]], [1.0, float("nan")], [float("inf")], ["not-a-number"]):
        with pytest.raises(ValueError):
            docs_search._query_vector(value)
    vector = docs_search._query_vector([0, 1.5, -2])
    assert vector.dtype.name == "float32"
    assert vector.tolist() == [0.0, 1.5, -2.0]


def test_search_closes_cursor_and_connection_after_fetch(monkeypatch):
    class Cursor:
        def __init__(self):
            self.closed = False

        def execute(self, sql, params):
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            self.closed = True

    class Connection:
        def __init__(self):
            self.cur = Cursor()
            self.closed = False

        def cursor(self):
            return self.cur

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(docs_search, "embed_one", lambda query, is_query: [0.1, 0.2])
    monkeypatch.setattr(docs_search, "connect_vec", lambda: connection)

    assert docs_search.search("S001 contract") == []
    assert connection.cur.closed is True
    assert connection.closed is True
