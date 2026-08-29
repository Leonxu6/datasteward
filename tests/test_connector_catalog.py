"""Source catalog and connector factory invariants."""

import pytest

from dm.connect.base import Source
from dm.connect.catalog import get_connector, get_source
from dm.connect.file import FileConnector


def test_get_connector_accepts_source_objects_without_sharing_mutable_state():
    source = Source(name="drop", source_type="file", params={"dir": "/tmp/drop"})

    connector = get_connector(source)

    assert isinstance(connector, FileConnector)
    assert connector.source == source
    assert connector.source is not source
    connector.source.params["dir"] = "/tmp/changed"
    assert source.params["dir"] == "/tmp/drop"


def test_get_connector_rejects_unknown_source_names():
    with pytest.raises(KeyError, match="未知源"):
        get_connector("missing-source")


@pytest.mark.parametrize("value", [None, 123, {}, [], object()])
def test_get_connector_rejects_unsupported_argument_types(value):
    with pytest.raises(TypeError, match="源名称或 Source"):
        get_connector(value)


def test_get_source_rejects_non_string_names():
    with pytest.raises(TypeError, match="源名称必须是字符串"):
        get_source(123)
