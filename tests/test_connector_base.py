"""Connector base-class invariants."""

import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector
from dm.connect.postgres import PostgresConnector
from dm.connect.sqlserver import SqlServerConnector


def test_connector_accepts_matching_source_types():
    assert PostgresConnector(Source(name="pg", source_type="postgres")).source.source_type == "postgres"
    assert SqlServerConnector(Source(name="u8", source_type="sqlserver")).source.source_type == "sqlserver"
    assert FileConnector(Source(name="drop", source_type="file")).source.source_type == "file"


@pytest.mark.parametrize(
    ("connector_cls", "source_type"),
    [
        (PostgresConnector, "sqlserver"),
        (SqlServerConnector, "file"),
        (FileConnector, "postgres"),
    ],
)
def test_connector_rejects_mismatched_source_types(connector_cls, source_type):
    with pytest.raises(ValueError, match="不匹配"):
        connector_cls(Source(name="wrong", source_type=source_type))


def test_connector_rejects_non_source_objects():
    with pytest.raises(TypeError, match="Source"):
        FileConnector({"source_type": "file"})
