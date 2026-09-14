"""Fast MCP compatibility smoke test that does not require the data stack."""
from importlib import import_module


def test_mcp_server_imports_with_declared_runtime_dependency():
    module = import_module("dm.connector.mcp_server")

    assert module.mcp is not None
    assert callable(module.list_tables)
    assert callable(module.run_sql)
