import pytest

from dm.tools.identity import normalize_identity_text


def test_identity_field_labels_have_a_bounded_length():
    assert normalize_identity_text("value", field_name="f" * 80) == "value"
    with pytest.raises(ValueError, match="80"):
        normalize_identity_text("value", field_name="f" * 81)
