import pytest

from dm.security.policy import apply_mask


def test_apply_mask_rejects_scalar_and_duplicate_column_shapes():
    with pytest.raises(ValueError, match="sequence of column names"):
        apply_mask("phone", [("123",)], ["phone"])
    with pytest.raises(ValueError, match="must not contain duplicates"):
        apply_mask(["phone", "phone"], [("123", "456")], ["phone"])


def test_apply_mask_rejects_string_rows_instead_of_treating_them_as_sequences():
    with pytest.raises(ValueError, match="row sequences"):
        apply_mask(["phone"], ["123"], ["phone"])
