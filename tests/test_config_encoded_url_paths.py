import pytest

from dm.config_validation import env_http_url


def test_env_http_url_rejects_encoded_path_traversal(monkeypatch):
    for value in (
        "https://example.com/%2e%2e/admin",
        "https://example.com/%2E/admin",
        "https://example.com/safe%2f..%2fadmin",
        "https://example.com/%5cadmin",
        "https://example.com/%0aadmin",
    ):
        monkeypatch.setenv("DM_URL", value)
        with pytest.raises(ValueError):
            env_http_url("DM_URL", "http://localhost")


def test_env_http_url_rejects_encoded_slash_separators(monkeypatch):
    for value in (
        "https://example.com/api%2Fv1",
        "https://example.com/api%2fv1",
    ):
        monkeypatch.setenv("DM_URL", value)
        with pytest.raises(ValueError, match="编码后的斜杠"):
            env_http_url("DM_URL", "http://localhost")


def test_env_http_url_keeps_benign_percent_encoding(monkeypatch):
    monkeypatch.setenv("DM_URL", "https://example.com/models/%7Eqwen")
    assert env_http_url("DM_URL", "http://localhost") == "https://example.com/models/%7Eqwen"
