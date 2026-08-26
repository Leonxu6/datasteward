import pytest
from dm.llm import _validate_messages

def test_message_roles_accept_openai_compatible_roles():
    for role in ('system','user','assistant','tool','function','developer'):
        assert _validate_messages([{'role':role,'content':'ok'}])[0]['role']==role

def test_message_roles_reject_unknown_role():
    with pytest.raises(ValueError,match='不受支持'):_validate_messages([{'role':'root','content':'x'}])
