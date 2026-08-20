"""Source credential environment references should fail early and predictably."""

import pytest

from dm.connect.base import Source


def test_source_secret_reads_configured_environment(monkeypatch):
    monkeypatch.setenv("DM_TEST_SECRET", "s3cr3t")
    source = Source(
        name="test",
        source_type="file",
        credential_env={"password": "DM_TEST_SECRET"},
    )

    assert source.secret("password") == "s3cr3t"


def test_source_secret_uses_default_when_reference_is_missing():
    source = Source(name="test", source_type="file")

    assert source.secret("password", "fallback") == "fallback"


@pytest.mark.parametrize("env_name", [None, 123, "", " DM_SECRET", "DM_SECRET ", "DM=SECRET", "DM\x00SECRET"])
def test_source_secret_rejects_invalid_environment_references(env_name):
    source = Source(
        name="test",
        source_type="file",
        credential_env={"password": env_name},
    )

    with pytest.raises(ValueError, match="credential_env"):
        source.secret("password")
