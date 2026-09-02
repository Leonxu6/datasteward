import math

import pytest

from dm.llm import _validate_messages


def test_message_payload_rejects_nonstandard_json_numbers():
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="标准 JSON"):
            _validate_messages([{"role": "user", "content": {"score": value}}])


def test_message_payload_still_accepts_finite_numbers():
    messages = [{"role": "user", "content": {"score": 0.5}}]
    assert _validate_messages(messages) is messages
