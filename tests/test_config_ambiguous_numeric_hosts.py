import pytest

from dm.config_validation import env_http_url


@pytest.mark.parametrize(
    "host",
    ["2130706433", "127.1", "0x7f.0x0.0x0.0x1"],
)
def test_service_urls_reject_historical_numeric_host_spellings(monkeypatch, host):
    monkeypatch.setenv("DM_TEST_URL", f"http://{host}:9030")
    with pytest.raises(ValueError, match="主机名"):
        env_http_url("DM_TEST_URL", "http://localhost:9030")


def test_service_urls_keep_canonical_ipv4_literals(monkeypatch):
    monkeypatch.setenv("DM_TEST_URL", "http://127.0.0.1:9030")
    assert env_http_url("DM_TEST_URL", "http://localhost:9030") == "http://127.0.0.1:9030"
