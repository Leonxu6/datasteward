import pytest
from dm.config_validation import env_float,env_int

def test_env_int_rejects_pathological_digit_strings(monkeypatch):
    monkeypatch.setenv('DM_TEST_INT','9'*1000)
    with pytest.raises(ValueError,match='数字文本过长'):env_int('DM_TEST_INT',1,minimum=0,maximum=10)

def test_env_float_rejects_pathological_numeric_strings(monkeypatch):
    monkeypatch.setenv('DM_TEST_FLOAT','1'*1000)
    with pytest.raises(ValueError,match='数字文本过长'):env_float('DM_TEST_FLOAT',1.0,minimum=0.0,maximum=10.0)
