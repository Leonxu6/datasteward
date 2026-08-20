"""连接配置规范化的纯单元测试。"""

import pytest

from dm.connect.validation import normalize_env_name, normalize_identifier, normalize_required_text


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


def test_env_name_accepts_normal_environment_references():
    assert normalize_env_name("DM_SRC_PG_PASSWORD") == "DM_SRC_PG_PASSWORD"
    assert normalize_env_name("vendor.secret-name") == "vendor.secret-name"


@pytest.mark.parametrize("value", [None, "", " DM_SECRET", "DM_SECRET ", "DM=SECRET", "DM\x00SECRET"])
def test_env_name_rejects_invalid_environment_references(value):
    with pytest.raises(ValueError):
        normalize_env_name(value)


@pytest.mark.parametrize("value", ["Order Items", "order-items", "select", "库存 明细", 'quoted"name', "bracket]name"])
def test_identifier_accepts_values_that_can_be_safely_quoted(value):
    assert normalize_identifier(value, field_name="table") == value


@pytest.mark.parametrize("value", [None, 123, "", " table", "table ", "table\x00name", "table\nname"])
def test_identifier_rejects_unusable_values(value):
    with pytest.raises(ValueError):
        normalize_identifier(value, field_name="table")
