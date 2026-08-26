import pytest
from dm.llm import _gateway_base_url

def test_gateway_rejects_dangling_and_zero_ports():
    for value in ('https://example.com:','https://example.com:0'):
        with pytest.raises(ValueError):_gateway_base_url(value)

def test_gateway_rejects_whitespace_and_backslashes():
    for value in ('https://exa mple.com','https:\\example.com'):
        with pytest.raises(ValueError):_gateway_base_url(value)
