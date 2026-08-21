from types import SimpleNamespace

import pytest

from dm.connect.base import ColumnDef, DatasetDef
from dm.connect.u8_mapping import _sr_ddl


def test_u8_ddl_requires_columns():
    dataset = DatasetDef(name="Inventory", columns=[], primary_key=[])
    with pytest.raises(ValueError, match="没有可同步列"):
        _sr_ddl(dataset, ["cInvCode"])


def test_u8_ddl_requires_known_primary_key_columns():
    dataset = DatasetDef(
        name="Inventory",
        columns=[ColumnDef(name="cInvCode", data_type="nvarchar")],
        primary_key=["missing"],
    )
    with pytest.raises(ValueError, match="主键列不在自省结果"):
        _sr_ddl(dataset, ["missing"])


def test_u8_ddl_places_primary_key_first_and_not_null():
    dataset = DatasetDef(
        name="Inventory",
        columns=[
            ColumnDef(name="cInvName", data_type="nvarchar"),
            ColumnDef(name="cInvCode", data_type="nvarchar"),
            ColumnDef(name="enabled", data_type="bit"),
        ],
        primary_key=["cInvCode"],
    )
    ddl = _sr_ddl(dataset, ["cInvCode"])
    assert "`cInvCode` VARCHAR(255) NOT NULL" in ddl
    assert "PRIMARY KEY(`cInvCode`)" in ddl
    assert ddl.index("`cInvCode`") < ddl.index("`cInvName`")
    assert "`enabled` BOOLEAN NULL" in ddl
