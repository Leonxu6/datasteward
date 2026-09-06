import pytest

from dm.tools.identity import normalize_identity_text


@pytest.mark.parametrize("value", ["agent\u202eadmin", "role\u2066hidden", "warehouse\u200f1"])
def test_identity_metadata_rejects_bidirectional_controls(value):
    with pytest.raises(ValueError, match="控制字符"):
        normalize_identity_text(value, field_name="identity")


@pytest.mark.parametrize("value", ["agent\u200cadmin", "role\u200dhidden", "warehouse\u206a1", "agent" + chr(0xD800)])
def test_identity_metadata_rejects_generic_format_and_surrogate_controls(value):
    with pytest.raises(ValueError, match="控制字符"):
        normalize_identity_text(value, field_name="identity")


def test_identity_field_labels_reject_bidirectional_controls():
    with pytest.raises(ValueError, match="control"):
        normalize_identity_text("agent", field_name="user\u202ename")


def test_identity_field_labels_reject_generic_format_controls():
    with pytest.raises(ValueError, match="control"):
        normalize_identity_text("agent", field_name="user\u200cname")
