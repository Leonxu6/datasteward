import math
import os

import pytest

from dm.config_validation import env_bool, env_float, env_http_url, env_int, env_text


def test_env_text_defaults_and_validates_padding_controls(monkeypatch):
    monkeypatch.delenv("DM_X", raising=False)
    assert env_text("DM_X", "default") == "default"
    for value in ("", " padded", "padded ", "bad\x00value"):
        monkeypatch.setenv("DM_X", value)
        with pytest.raises(ValueError):
            env_text("DM_X", "default")


def test_env_text_can_explicitly_allow_empty(monkeypatch):
    monkeypatch.setenv("DM_X", "")
    assert env_text("DM_X", "fallback", allow_empty=True) == ""


def test_env_text_validates_parser_options(monkeypatch):
    monkeypatch.delenv("DM_X", raising=False)
    for allow_empty in (0, 1, "true", None):
        with pytest.raises(ValueError):
            env_text("DM_X", "default", allow_empty=allow_empty)  # type: ignore[arg-type]
    for max_length in (0, -1, True, 1.5, "100"):
        with pytest.raises(ValueError):
            env_text("DM_X", "default", max_length=max_length)  # type: ignore[arg-type]


def test_env_int_requires_ascii_digits_and_bounds(monkeypatch):
    monkeypatch.setenv("DM_PORT", "9030")
    assert env_int("DM_PORT", 1, minimum=1, maximum=65535) == 9030
    for value in ("0", "65536", " 9030", "+9030", "９０３０", "9.0"):
        monkeypatch.setenv("DM_PORT", value)
        with pytest.raises(ValueError):
            env_int("DM_PORT", 1, minimum=1, maximum=65535)


def test_env_float_rejects_nonfinite_and_out_of_range_values(monkeypatch):
    monkeypatch.setenv("DM_TIMEOUT", "2.5")
    assert env_float("DM_TIMEOUT", 1, minimum=0.1, maximum=60) == 2.5
    for value in ("nan", "inf", "0", "61", "bad"):
        monkeypatch.setenv("DM_TIMEOUT", value)
        with pytest.raises(ValueError):
            env_float("DM_TIMEOUT", 1, minimum=0.1, maximum=60)


def test_env_bool_requires_explicit_supported_spellings(monkeypatch):
    for value, expected in (("1", True), ("true", True), ("YES", True), ("0", False), ("off", False)):
        monkeypatch.setenv("DM_FLAG", value)
        assert env_bool("DM_FLAG", False) is expected
    for value in ("maybe", " true", ""):
        monkeypatch.setenv("DM_FLAG", value)
        with pytest.raises(ValueError):
            env_bool("DM_FLAG", False)


def test_env_http_url_requires_http_host_and_no_embedded_credentials(monkeypatch):
    monkeypatch.setenv("DM_URL", "https://example.com/api/")
    assert env_http_url("DM_URL", "http://localhost") == "https://example.com/api"
    for value in ("file:///tmp/x", "https:///missing", "https://u:p@example.com", "https://example.com:bad"):
        monkeypatch.setenv("DM_URL", value)
        with pytest.raises(ValueError):
            env_http_url("DM_URL", "http://localhost")
