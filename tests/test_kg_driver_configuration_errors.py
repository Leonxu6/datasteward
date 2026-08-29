import sys
from types import SimpleNamespace

import pytest

from dm.kg import store


def test_driver_does_not_retry_genuine_value_errors(monkeypatch):
    calls = []

    class FakeGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            calls.append((args, kwargs))
            raise ValueError("invalid URI")

    monkeypatch.setitem(sys.modules, "neo4j", SimpleNamespace(GraphDatabase=FakeGraphDatabase))

    with pytest.raises(ValueError, match="invalid URI"):
        store.driver()

    assert len(calls) == 1
