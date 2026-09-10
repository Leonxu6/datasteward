import pytest

from dm.kg import store


def test_graph_queries_reject_malformed_text_before_opening_driver(monkeypatch):
    monkeypatch.setattr(store, "driver", lambda: pytest.fail("driver should not be opened"))
    for value in (None, "", "   ", "MATCH\x00(n) RETURN n"):
        with pytest.raises(ValueError):
            store.run_read(value)
        with pytest.raises(ValueError):
            store.run_write(value)


@pytest.mark.parametrize("control", ["\u200d", "\u206a", chr(0xD800)])
def test_graph_queries_reject_hidden_unicode_controls_before_opening_driver(monkeypatch, control):
    monkeypatch.setattr(store, "driver", lambda: pytest.fail("driver should not be opened"))
    with pytest.raises(ValueError, match="control"):
        store.run_read(f"MATCH (n){control} RETURN n")
    with pytest.raises(ValueError, match="control"):
        store.run_write(f"MATCH (n){control} RETURN n")


def test_graph_query_size_is_bounded_by_utf8_bytes(monkeypatch):
    monkeypatch.setattr(store, "driver", lambda: pytest.fail("driver should not be opened"))
    monkeypatch.setattr(store, "_MAX_CYPHER_BYTES", 5)
    assert len("返 回".encode("utf-8")) > 5
    with pytest.raises(ValueError, match="UTF-8 bytes"):
        store.run_read("返 回")


def test_graph_queries_allow_newline_formatted_cypher(monkeypatch):
    calls = []

    class Result:
        def __iter__(self):
            return iter([])

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def run(self, cypher, **params):
            calls.append((cypher, params))
            return Result()

    class Driver:
        def session(self):
            return Session()

        def close(self):
            pass

    monkeypatch.setattr(store, "driver", Driver)
    query = "MATCH (n)\nRETURN n"
    assert store.run_read(query, limit=1) == []
    assert calls == [(query, {"limit": 1})]
