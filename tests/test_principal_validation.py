import pytest

from dm.tools.principal import Principal


def test_principal_accepts_normal_governance_metadata():
    principal = Principal(
        user="张三",
        role="采购",
        purpose="库存分析",
        session_id="session-123",
        channel="dingtalk",
        warehouse_id="W01",
    )
    user = principal.to_user()
    assert user.name == "张三"
    assert user.role == "采购"
    assert user.attrs == {"warehouse_id": "W01"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"user": ""},
        {"user": " padded"},
        {"role": ""},
        {"purpose": "bad\npurpose"},
        {"session_id": "bad\x00session"},
        {"channel": "web ui"},
        {"warehouse_id": " W01"},
    ],
)
def test_principal_rejects_ambiguous_or_log_poisoning_metadata(kwargs):
    with pytest.raises(ValueError):
        Principal(**kwargs)
