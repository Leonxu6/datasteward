import pytest

from dm.app.errors import safe_error_summary


def test_safe_error_summary_redacts_exception_text():
    message = safe_error_summary("加载数据", RuntimeError("postgres://user:secret@host/db"))
    assert message == "加载数据失败（RuntimeError）"
    assert "secret" not in message


def test_safe_error_summary_normalizes_operation_text():
    assert safe_error_summary("  模块\n渲染  ", ValueError("x")) == "模块 渲染失败（ValueError）"


def test_safe_error_summary_neutralizes_hidden_unicode_controls():
    message = safe_error_summary("模块\u200d渲染\ud800", ValueError("x"))
    assert message == "模块 渲染失败（ValueError）"
    assert "\u200d" not in message
    assert "\ud800" not in message


def test_safe_error_summary_rejects_empty_operation():
    with pytest.raises(ValueError):
        safe_error_summary("   ", RuntimeError())
    with pytest.raises(ValueError):
        safe_error_summary("\u200d\ud800", RuntimeError())
