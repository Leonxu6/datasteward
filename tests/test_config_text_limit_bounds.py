import pytest

from dm.config_validation import env_text


def test_text_parser_rejects_unbounded_caller_limits(monkeypatch):
    monkeypatch.delenv("DM_TEST_TEXT", raising=False)
    with pytest.raises(ValueError, match="100000"):
        env_text("DM_TEST_TEXT", "ok", max_length=100_001)


def test_text_parser_preserves_normal_custom_limits(monkeypatch):
    monkeypatch.setenv("DM_TEST_TEXT", "value")
    assert env_text("DM_TEST_TEXT", "default", max_length=5) == "value"
