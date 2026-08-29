import pytest

from dm.tools.identity import normalize_identity_text


def test_identity_normalizer_rejects_invalid_field_names():
    for field_name in (None, "", " field", "field ", "field\n"):
        with pytest.raises(ValueError):
            normalize_identity_text("alice", field_name=field_name)


def test_identity_normalizer_requires_positive_integer_limits():
    for limit in (0, -1, True, 1.5, "20"):
        with pytest.raises(ValueError, match="max_length"):
            normalize_identity_text("alice", field_name="user", max_length=limit)


def test_identity_normalizer_requires_boolean_empty_policy():
    for allow_empty in (0, 1, "true", None):
        with pytest.raises(ValueError, match="allow_empty"):
            normalize_identity_text("alice", field_name="user", allow_empty=allow_empty)


def test_identity_normalizer_keeps_existing_text_contract():
    assert normalize_identity_text(None, field_name="purpose", default="") == ""
    with pytest.raises(ValueError):
        normalize_identity_text(" alice", field_name="user")
    with pytest.raises(ValueError):
        normalize_identity_text("", field_name="user", allow_empty=False)
