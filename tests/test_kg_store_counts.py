import pytest

from dm.kg import store


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def single(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class Session:
    def __init__(self, results):
        self.results = iter(results)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, _cypher):
        return Result(next(self.results))


class Driver:
    def __init__(self, results):
        self.results = results
        self.closed = False

    def session(self):
        return Session(self.results)

    def close(self):
        self.closed = True


def _run_counts(monkeypatch, results):
    driver = Driver(results)
    monkeypatch.setattr(store, "driver", lambda: driver)
    try:
        return store.counts()
    finally:
        assert driver.closed


def test_counts_accepts_well_formed_statistics(monkeypatch):
    assert _run_counts(
        monkeypatch,
        [[{"c": 3}], [{"c": 2}], [{"label": "Customer", "c": 3}], [{"t": "BUYS", "c": 2}], [{"c": 1}]],
    ) == {"nodes": 3, "edges": 2, "by_label": {"Customer": 3}, "by_rel": {"BUYS": 2}, "doc_extracted": 1}


@pytest.mark.parametrize("node_row", [[], [{"c": -1}], [{"c": True}], [{"wrong": 1}]])
def test_counts_rejects_missing_or_invalid_scalar_counts(monkeypatch, node_row):
    with pytest.raises(RuntimeError):
        _run_counts(monkeypatch, [node_row, [{"c": 0}], [], [], [{"c": 0}]])


@pytest.mark.parametrize(
    "label_rows",
    [
        [{"label": "", "c": 1}],
        [{"label": " Customer", "c": 1}],
        [{"label": "Customer", "c": -1}],
        [{"label": "Customer", "c": 1}, {"label": "Customer", "c": 2}],
        [{"label": "Customer"}],
    ],
)
def test_counts_rejects_malformed_label_distributions(monkeypatch, label_rows):
    with pytest.raises(RuntimeError):
        _run_counts(monkeypatch, [[{"c": 1}], [{"c": 1}], label_rows, [], [{"c": 0}]])
