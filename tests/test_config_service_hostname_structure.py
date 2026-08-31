import pytest

from dm.config_validation import env_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://-db:9030",
        "http://db-:9030",
        "http://db..internal:9030",
        "http://数据库:9030",
        "http://" + "a" * 64 + ":9030",
    ],
)
def test_service_urls_reject_malformed_hostnames(monkeypatch, url):
    monkeypatch.setenv("DM_TEST_URL", url)
    with pytest.raises(ValueError, match="主机名"):
        env_http_url("DM_TEST_URL", "http://localhost:9030")


def test_service_urls_keep_local_service_aliases(monkeypatch):
    monkeypatch.setenv("DM_TEST_URL", "http://starrocks_fe:9030")
    assert env_http_url("DM_TEST_URL", "http://localhost:9030") == "http://starrocks_fe:9030"
