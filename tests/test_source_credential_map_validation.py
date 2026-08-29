import pytest

from dm.connect.base import Source


def test_source_secret_rejects_non_mapping_credential_registry():
    for registry in (None, [], "TOKEN", 7):
        source = Source(name="files", source_type="file", credential_env=registry)
        with pytest.raises(ValueError, match="credential_env"):
            source.secret("token")


def test_source_secret_rejects_invalid_environment_references():
    for env_name in ("", " TOKEN", "TOKEN ", "BAD NAME", "TOKEN\n"):
        source = Source(name="files", source_type="file", credential_env={"token": env_name})
        with pytest.raises(ValueError):
            source.secret("token")
