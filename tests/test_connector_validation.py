"""连接配置规范化的纯单元测试。"""

import pytest

from dm.connect.validation import normalize_required_text


def test_required_text_accepts_nonempty_values_without_padding():
    assert normalize_required_text("db.internal", field_name="host") == "db.internal"
    assert normalize_required_text("ERP Production", field_name="database") == "ERP Production"


@pytest.mark.parametrize("value", [None, 123, [], "", " ", "\tdb", "db ", "\ndb"])
def test_required_text_rejects_missing_nonstring_and_padded_values(value):
    with pytest.raises(ValueError):
        normalize_required_text(value, field_name="host")


@pytest.mark.parametrize("value", ["db\x00internal", "db\tinternal", "db\ninternal", "db\rinternal", "db\x7finternal"])
def test_required_text_rejects_embedded_control_characters(value):
    with pytest.raises(ValueError, match="控制字符"):
        normalize_required_text(value, field_name="host")
