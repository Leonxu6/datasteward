import pytest
from dm.llm import _gateway_base_url

def test_gateway_rejects_embedded_credentials():
    with pytest.raises(ValueError,match='凭据'):_gateway_base_url('https://user:secret@example.com')

def test_gateway_rejects_query_and_fragment():
    for value in ('https://example.com?token=secret','https://example.com#private'):
        with pytest.raises(ValueError,match='查询参数或片段'):_gateway_base_url(value)
