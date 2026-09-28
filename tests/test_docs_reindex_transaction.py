"""A failed vector write must not destroy the previously indexed document."""

import pytest

from dm.docs import index


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=None):
        self.connection.statements.append(statement)

    def executemany(self, statement, records):
        self.connection.statements.append(statement)
        if self.connection.fail_insert:
            raise RuntimeError("vector insert failed")

    def fetchall(self):
        return self.connection.rows

    def close(self):
        pass


class _Connection:
    def __init__(self, rows, *, fail_insert=False):
        self.rows = rows
        self.fail_insert = fail_insert
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.mark.parametrize("fail_insert", [False, True])
def test_reindex_replaces_chunks_and_marker_in_one_transaction(monkeypatch, tmp_path, fail_insert):
    source = tmp_path / "document.txt"
    source.write_text("A useful document", encoding="utf-8")
    connection = _Connection(
        [("DOC1", "manual", "Manual", "", str(source), "new-hash", "old-hash")],
        fail_insert=fail_insert,
    )
    monkeypatch.setattr(index, "init_schema", lambda: None)
    monkeypatch.setattr(index, "connect_vec", lambda *, autocommit: connection if autocommit is False else None)
    monkeypatch.setattr(index, "embed", lambda chunks: [[0.1, 0.2] for _ in chunks])
    monkeypatch.setattr(index, "counts", lambda: (1, 1))

    if fail_insert:
        with pytest.raises(RuntimeError, match="vector insert failed"):
            index.reindex(verbose=False)
        assert connection.commits == 0
        assert connection.rollbacks == 1
        assert not any(statement.startswith("UPDATE document") for statement in connection.statements)
    else:
        assert index.reindex(verbose=False) == (1, 1)
        assert connection.commits == 1
        assert connection.rollbacks == 0
        assert any(statement.startswith("UPDATE document") for statement in connection.statements)
    assert connection.closed
