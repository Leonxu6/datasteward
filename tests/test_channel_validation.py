import math

import pytest

from dm.channels.validation import (
    append_query_params,
    normalize_message_text,
    normalize_nonnegative_int,
    normalize_positive_float,
    normalize_positive_int,
    normalize_webhook_url,
)


def test_message_text_accepts_multiline_content_without_stripping_it():
    value = "line one\nline two\twith tab"
    assert normalize_message_text(value) == value


@pytest.mark.parametrize(
    "value",
    [None, 7, "", "   ", "bad\x00message", "bad\x08message", "bad\x1bmessage", "bad\x7fmessage"],
)
def test_message_text_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_message_text(value)


def test_message_text_enforces_explicit_length_limit():
    with pytest.raises(ValueError, match="不能超过"):
        normalize_message_text("12345", max_length=4)


def test_message_text_validates_field_name_and_length_options():
    for field_name in ("", " message", "message ", "bad\nname", None):
        with pytest.raises(ValueError):
            normalize_message_text("ok", field_name=field_name)  # type: ignore[arg-type]
    for max_length in (0, -1, True, 1.5, "20"):
        with pytest.raises(ValueError):
            normalize_message_text("ok", max_length=max_length)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["https://example.com/hook", "https://example.com/hook?access_token=abc"])
def test_webhook_url_accepts_https_hosts(value):
    assert normalize_webhook_url(value) == value


def test_webhook_url_validates_field_name():
    for field_name in ("", " webhook", "webhook ", "bad\nname", None):
        with pytest.raises(ValueError):
            normalize_webhook_url("https://example.com/hook", field_name=field_name)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com/hook",
        "https:///missing-host",
        "https://user:pass@example.com/hook",
        " https://example.com/hook",
        "https://example.com:bad/hook",
        "https://example.com\\@evil.test/hook",
        "https://example.com:/hook",
        "https://example.com:0/hook",
    ],
)
def test_webhook_url_rejects_unsafe_or_malformed_values(value):
    with pytest.raises(ValueError):
        normalize_webhook_url(value)


def test_append_query_params_preserves_existing_query_and_uses_one_separator():
    result = append_query_params("https://example.com/hook?access_token=abc", timestamp=123, sign="a+b=")
    assert result.startswith("https://example.com/hook?")
    assert "access_token=abc" in result
    assert "timestamp=123" in result
    assert "sign=a%2Bb%3D" in result
    assert "??" not in result


@pytest.mark.parametrize("value,expected", [(1, 1), ("2", 2), (10, 10)])
def test_positive_int_normalization(value, expected):
    assert normalize_positive_int(value, field_name="limit", default=4, maximum=10) == expected


@pytest.mark.parametrize("value", [True, 0, -1, 11, "1.5", " 2", "１２"])
def test_positive_int_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_positive_int(value, field_name="limit", default=4, maximum=10)


def test_nonnegative_int_allows_explicit_zero_capacity():
    assert normalize_nonnegative_int(0, field_name="queue_max", default=12, maximum=100) == 0
    assert normalize_nonnegative_int("12", field_name="queue_max", default=4, maximum=100) == 12


@pytest.mark.parametrize("value", [True, -1, 101, "-1", "1.5", " 2", "１２"])
def test_nonnegative_int_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_nonnegative_int(value, field_name="queue_max", default=12, maximum=100)


def test_positive_float_normalization_and_bounds():
    assert normalize_positive_float("2.5", field_name="timeout", default=3, maximum=10) == 2.5
    for value in (True, 0, -1, 11, math.inf, math.nan, "bad", " 2.5", "2.5 ", 10**10000):
        with pytest.raises(ValueError):
            normalize_positive_float(value, field_name="timeout", default=3, maximum=10)
