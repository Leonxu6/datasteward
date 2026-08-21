import pytest

from dm.tools.identity import normalize_channel, normalize_identity_text


def test_identity_text_accepts_unicode_and_explicit_empty_values():
    assert normalize_identity_text("张三", field_name="user", allow_empty=False) == "张三"
    assert normalize_identity_text("", field_name="purpose") == ""


@pytest.mark.parametrize("value", [None, "", " user", "user ", "bad\nuser", "x" * 201])
def test_required_identity_text_rejects_ambiguous_values(value):
    with pytest.raises(ValueError):
        normalize_identity_text(value, field_name="user", allow_empty=False)


def test_identity_text_uses_default_for_none_when_allowed():
    assert normalize_identity_text(None, field_name="purpose", default="analysis") == "analysis"


@pytest.mark.parametrize("value", ["mcp", "dingtalk", "web-ui", "api_v2"])
def test_channel_accepts_machine_readable_labels(value):
    assert normalize_channel(value) == value


@pytest.mark.parametrize("value", ["", " web", "web ui", "web/ui", "bad\nchannel", "x" * 41])
def test_channel_rejects_ambiguous_labels(value):
    with pytest.raises(ValueError):
        normalize_channel(value)
