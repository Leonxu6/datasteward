import pytest

from dm.config_validation import env_text


@pytest.mark.parametrize("control", ["\u202e", "\u2066", "\u200f"])
def test_text_settings_reject_bidirectional_controls(monkeypatch, control):
    monkeypatch.setenv("DM_TEST_TEXT", f"safe{control}hidden")
    with pytest.raises(ValueError, match="控制字符"):
        env_text("DM_TEST_TEXT", "fallback")
