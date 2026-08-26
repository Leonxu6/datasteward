import pytest
from dm.llm import _nonstream_content,_stream_content

def test_nonstream_shape_error_does_not_echo_payload():
    secret='super-secret-token'
    with pytest.raises(RuntimeError) as exc:_nonstream_content({'secret':secret})
    assert secret not in str(exc.value)

def test_stream_error_does_not_echo_payload():
    secret='super-secret-token'
    with pytest.raises(RuntimeError) as exc:_stream_content({'error':secret})
    assert secret not in str(exc.value)
