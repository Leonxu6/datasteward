import pytest

from dm.tools.sql_guard import validate_readonly


@pytest.mark.parametrize("control", ["\u202e", "\u2066", "\u200f"])
def test_readonly_sql_rejects_bidirectional_controls(control):
    clean, error = validate_readonly(f"SELECT 1 {control}")
    assert clean == ""
    assert "控制字符" in error
