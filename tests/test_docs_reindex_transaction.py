"""A failed vector write must not destroy the previously indexed document."""

from datetime import datetime, timezone

import pytest

from dm.docs import index


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=None):
        self.connection.statements.append(statement)
        self.connection.params.append(params)

    def executemany(self, statement, records):
        self.connection.statements.append(statement)
        if self.connection.fail_insert:
            raise RuntimeError("vector insert failed")

    def fetchmany(self, size):
        self.connection.fetch_sizes.append(size)
        return self.connection.rows[:size]

    def close(self):
        self.connection.closed_cursors += 1


class _Connection:
    def __init__(self, rows, *, fail_insert=False):
        self.rows = rows
        self.fail_insert = fail_insert
        self.statements = []
        self.params = []
        self.fetch_sizes = []
        self.closed_cursors = 0
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
    assert connection.fetch_sizes == [index._MAX_DOCUMENT_CATALOG_ROWS + 1]


@pytest.mark.parametrize("embeddings", [[], [[0.1], [0.2]], None])
def test_reindex_rejects_incomplete_embedding_batches_before_deleting_old_chunks(
    monkeypatch, tmp_path, embeddings
):
    source = tmp_path / "document.txt"
    source.write_text("A useful document", encoding="utf-8")
    connection = _Connection(
        [("DOC1", "manual", "Manual", "", str(source), "new-hash", "old-hash")]
    )
    monkeypatch.setattr(index, "init_schema", lambda: None)
    monkeypatch.setattr(index, "connect_vec", lambda *, autocommit: connection)
    monkeypatch.setattr(index, "embed", lambda chunks: embeddings)

    with pytest.raises(RuntimeError, match="unexpected vector count"):
        index.reindex(verbose=False)

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert not any(statement.startswith("DELETE FROM doc_chunk") for statement in connection.statements)
    assert connection.closed


def test_reindex_allows_nullable_document_title_in_verbose_output(monkeypatch, tmp_path, capsys):
    source = tmp_path / "document.txt"
    source.write_text("A useful document", encoding="utf-8")
    connection = _Connection(
        [("DOC1", "manual", None, "", str(source), "new-hash", "old-hash")]
    )
    monkeypatch.setattr(index, "init_schema", lambda: None)
    monkeypatch.setattr(index, "connect_vec", lambda *, autocommit: connection)
    monkeypatch.setattr(index, "embed", lambda chunks: [[0.1, 0.2] for _ in chunks])
    monkeypatch.setattr(index, "counts", lambda: (1, 1))

    assert index.reindex(verbose=True) == (1, 1)
    assert "DOC1 «»" in capsys.readouterr().out
    assert connection.commits == 1
    assert connection.closed


def test_reindex_persists_a_utc_derived_naive_database_timestamp(monkeypatch, tmp_path):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc
            return cls(2026, 10, 13, 9, 30, tzinfo=timezone.utc)

    source = tmp_path / "document.txt"
    source.write_text("A useful document", encoding="utf-8")
    connection = _Connection(
        [("DOC1", "manual", "Manual", "", str(source), "new-hash", "old-hash")]
    )
    monkeypatch.setattr(index, "datetime", FrozenDateTime)
    monkeypatch.setattr(index, "init_schema", lambda: None)
    monkeypatch.setattr(index, "connect_vec", lambda *, autocommit: connection)
    monkeypatch.setattr(index, "embed", lambda chunks: [[0.1, 0.2] for _ in chunks])
    monkeypatch.setattr(index, "counts", lambda: (1, 1))

    assert index.reindex(verbose=False) == (1, 1)

    update_params = next(
        params for params in connection.params
        if isinstance(params, tuple) and len(params) == 4 and params[0] == "new-hash"
    )
    assert update_params[2] == datetime(2026, 10, 13, 9, 30)
    assert update_params[2].tzinfo is None


def test_reindex_rejects_an_oversized_catalog_before_loading_sources(monkeypatch):
    row = ("DOC1", "manual", "Manual", "", "/unused", "new-hash", "old-hash")
    connection = _Connection([row] * (index._MAX_DOCUMENT_CATALOG_ROWS + 1))
    monkeypatch.setattr(index, "init_schema", lambda: None)
    monkeypatch.setattr(index, "connect_vec", lambda *, autocommit: connection)
    monkeypatch.setattr(
        index,
        "read_document_source",
        lambda path: pytest.fail("an oversized catalog must fail before reading document files"),
    )

    with pytest.raises(RuntimeError, match="document catalog exceeds"):
        index.reindex(verbose=False)

    assert connection.commits == 0
    assert connection.closed
    assert connection.closed_cursors == 2


def test_status_bounds_catalog_reads_and_closes_cursor_and_connection(monkeypatch, capsys):
    connection = _Connection(
        [("DOC1", "manual", 1, "", "已索引", "Manual")]
    )
    monkeypatch.setattr(index, "counts", lambda: (1, 1))
    monkeypatch.setattr(index, "connect", lambda: connection)

    index.status()

    assert "DOC1" in capsys.readouterr().out
    assert connection.fetch_sizes == [index._MAX_DOCUMENT_CATALOG_ROWS + 1]
    assert connection.closed_cursors == 1
    assert connection.closed


def test_document_catalog_rejects_malformed_rows():
    connection = _Connection([("DOC1", "manual")])

    with pytest.raises(RuntimeError, match="malformed row"):
        index._read_document_catalog(connection.cursor(), row_width=7)
