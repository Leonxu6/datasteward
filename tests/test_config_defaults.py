from urllib.parse import urlsplit

from dm import config


def test_default_ports_and_timeouts_stay_within_supported_ranges():
    assert 1 <= config.WH_PORT <= 65535
    assert 1 <= config.SRC_PG_PORT <= 65535
    assert 1 <= config.SRC_MSSQL_PORT <= 65535
    assert 0.1 <= config.LLM_CONNECT_TIMEOUT <= 3600
    assert 0.1 <= config.LLM_READ_TIMEOUT <= 3600
    assert 0.1 <= config.LLM_WALL_TIMEOUT <= 86400
    assert 1 <= config.LLM_MAX_TOKENS <= 131072


def test_service_urls_have_http_scheme_and_hostname():
    for value in (config.FLINK_REST, config.FLINK_URL, config.LLM_BASE_URL):
        parsed = urlsplit(value)
        assert parsed.scheme in {"http", "https"}
        assert parsed.hostname


def test_default_data_paths_are_path_objects_and_log_dir_is_nested():
    assert config.DATA_DIR.is_absolute()
    assert config.LOG_DIR.parent == config.DATA_DIR
