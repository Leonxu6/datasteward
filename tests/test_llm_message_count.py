import pytest
from dm.llm import _MAX_MESSAGES,_validate_messages

def test_message_batch_accepts_limit():
    messages=[{'role':'user','content':'x'} for _ in range(_MAX_MESSAGES)];assert len(_validate_messages(messages))==_MAX_MESSAGES

def test_message_batch_rejects_over_limit():
    messages=[{'role':'user','content':'x'} for _ in range(_MAX_MESSAGES+1)]
    with pytest.raises(ValueError,match='不能超过'):_validate_messages(messages)
