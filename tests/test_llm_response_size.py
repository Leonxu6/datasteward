import pytest
from dm.llm import _MAX_RESPONSE_CHARS,_nonstream_content

def test_nonstream_content_accepts_bounded_text():
    assert _nonstream_content({'choices':[{'message':{'content':'ok'}}]})=='ok'

def test_nonstream_content_rejects_oversized_text():
    data={'choices':[{'message':{'content':'x'*(_MAX_RESPONSE_CHARS+1)}}]}
    with pytest.raises(RuntimeError,match='大小上限'):_nonstream_content(data)
