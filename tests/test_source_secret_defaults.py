import pytest

from dm.connect.base import Source


def test_source_secret_rejects_non_text_defaults(monkeypatch):
    source = Source(name="files", source_type="file")
    for default in (None, 7, False, ["token"]):
        with pytest.raises(ValueError, match="default"):
            source.secret("token", default)


def test_source_secret_returns_text_fallback_when_reference_is_missing():
    source = Source(name="files", source_type="file")
    assert source.secret("token", "fallback") == "fallback"


def test_source_secret_reads_validated_environment_reference(monkeypatch):
    source = Source(name="files", source_type="file", credential_env={"token": "TEST_SOURCE_TOKEN"})
    monkeypatch.setenv("TEST_SOURCE_TOKEN", "secret-value")
    assert source.secret("token", "fallback") == "secret-value"
