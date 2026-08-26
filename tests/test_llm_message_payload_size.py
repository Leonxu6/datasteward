import pytest
from dm.llm import _MAX_SERIALIZED_MESSAGES,_validate_messages

def test_message_payload_rejects_oversized_serialization():
    content='x'*(_MAX_SERIALIZED_MESSAGES+1)
    with pytest.raises(ValueError,match='序列化后过大'):_validate_messages([{'role':'user','content':content}])
