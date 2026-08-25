import math
import os

import pytest

from dm.config_validation import env_bool, env_float, env_http_url, env_int, env_text


def test_env_text_defaults_and_validates_padding_controls(monkeypatch):
    monkeypatch.delenv("DM_X", raising=False)
    assert env_text("DM_X", "default") == "default"
    for value in ("", " padded", "padded "):
        monkeypatch.setenv("DM_X", value)
        with pytest.raises(ValueError):
            env_text("DM_X", "default")

    # Operating systems reject NUL bytes before they can enter an environment
    # variable, so exercise the same text validator through its default path.
    monkeypatch.delenv("DM_X", raising=False)
    with pytest.raises(ValueError, match="控制字符"):
        env_text("DM_X", "bad\x00value")


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
    for value, expected in (("9030", 9030), ("-2", -2), ("0", 0)):
        monkeypatch.setenv("DM_PORT", value)
        assert env_int("DM_PORT", 1, minimum=-2, maximum=65535) == expected
    for value in ("65536", "-3", " 9030", "+9030", "--2", "９０３０", "9.0"):
        monkeypatch.setenv("DM_PORT", value)
        with pytest.raises(ValueError):
            env_int("DM_PORT", 1, minimum=-2, maximum=65535)


def test_env_int_validates_defaults_and_bounds(monkeypatch):
    monkeypatch.delenv("DM_PORT", raising=False)
    for default in (True, False, 3.0, "3", None):
        with pytest.raises(ValueError):
            env_int("DM_PORT", default, minimum=1, maximum=10)  # type: ignore[arg-type]
    for minimum, maximum in ((True, 10), (1, False), (1.5, 10), (1, "10"), (11, 10)):
        with pytest.raises(ValueError):
            env_int("DM_PORT", 3, minimum=minimum, maximum=maximum)  # type: ignore[arg-type]


def test_env_float_rejects_nonfinite_out_of_range_and_padded_values(monkeypatch):
    monkeypatch.setenv("DM_TIMEOUT", "2.5")
    assert env_float("DM_TIMEOUT", 1, minimum=0.1, maximum=60) == 2.5
    for value in ("nan", "inf", "0", "61", "bad", " 2.5", "2.5 ", "\t2.5"):
        monkeypatch.setenv("DM_TIMEOUT", value)
        with pytest.raises(ValueError):
            env_float("DM_TIMEOUT", 1, minimum=0.1, maximum=60)


def test_env_float_validates_defaults_and_bounds(monkeypatch):
    monkeypatch.delenv("DM_TIMEOUT", raising=False)
    for default in (True, False, "1", None, math.nan, math.inf):
        with pytest.raises(ValueError):
            env_float("DM_TIMEOUT", default, minimum=0.1, maximum=60)  # type: ignore[arg-type]
    cases = ((True, 60), (0.1, False), ("0.1", 60), (0.1, "60"), (math.nan, 60), (0.1, math.inf), (61, 60))
    for minimum, maximum in cases:
        with pytest.raises(ValueError):
            env_float("DM_TIMEOUT", 1, minimum=minimum, maximum=maximum)  # type: ignore[arg-type]


def test_env_float_normalizes_huge_integer_overflow(monkeypatch):
    huge = 10**10000
    monkeypatch.delenv("DM_TIMEOUT", raising=False)
    for default, minimum, maximum in ((huge, 0.1, 60), (1, -huge, 60), (1, 0.1, huge)):
        with pytest.raises(ValueError):
            env_float("DM_TIMEOUT", default, minimum=minimum, maximum=maximum)


def test_env_bool_requires_explicit_supported_spellings(monkeypatch):
    for value, expected in (("1", True), ("true", True), ("YES", True), ("0", False), ("off", False)):
        monkeypatch.setenv("DM_FLAG", value)
        assert env_bool("DM_FLAG", False) is expected
    for value in ("maybe", " true", ""):
        monkeypatch.setenv("DM_FLAG", value)
        with pytest.raises(ValueError):
            env_bool("DM_FLAG", False)


def test_env_bool_validates_default_type(monkeypatch):
    monkeypatch.delenv("DM_FLAG", raising=False)
    for default in (0, 1, "true", None):
        with pytest.raises(ValueError):
            env_bool("DM_FLAG", default)  # type: ignore[arg-type]


def test_env_http_url_requires_clean_service_base(monkeypatch):
    monkeypatch.setenv("DM_URL", "https://example.com/api/")
    assert env_http_url("DM_URL", "http://localhost") == "https://example.com/api"
    invalid = (
        "file:///tmp/x",
        "https:///missing",
        "https://u:p@example.com",
        "https://example.com:bad",
        "https://example.com/a b",
        "https://example.com\\@evil.test/path",
        "https://example.com/api?token=1",
        "https://example.com/api#section",
    )
    for value in invalid:
        monkeypatch.setenv("DM_URL", value)
        with pytest.raises(ValueError):
            env_http_url("DM_URL", "http://localhost")
