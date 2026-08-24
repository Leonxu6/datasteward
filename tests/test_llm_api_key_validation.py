import pytest

import dm.llm as llm


def test_header_value_allows_empty_or_clean_api_keys():
    assert llm._header_value("", field_name="LLM_API_KEY") == ""
    assert llm._header_value("token-123", field_name="LLM_API_KEY") == "token-123"


@pytest.mark.parametrize("value", [" token", "token ", "token\tvalue", "token\nvalue"])
def test_header_value_rejects_padded_or_control_character_api_keys(value):
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        llm._header_value(value, field_name="LLM_API_KEY")
