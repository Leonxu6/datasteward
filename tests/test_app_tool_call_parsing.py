import pytest

from dm.app.data import parse_tool_call


def test_parse_tool_call_accepts_object_arguments():
    name, args = parse_tool_call('mcp__dm__run_sql  {"sql":"SELECT 1","limit":5}')
    assert name == "run_sql"
    assert args == {"sql": "SELECT 1", "limit": 5}


@pytest.mark.parametrize(
    "payload",
    [
        '["not","an","object"]',
        'NaN',
        '{"limit":NaN}',
        '{"sql":"safe","sql":"overwritten"}',
        'not-json',
    ],
)
def test_parse_tool_call_rejects_ambiguous_or_non_object_arguments(payload):
    name, args = parse_tool_call(f"mcp__dm__run_sql  {payload}")
    assert name == "run_sql"
    assert args == {}
