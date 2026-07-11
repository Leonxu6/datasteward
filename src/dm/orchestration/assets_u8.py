"""U8 → ODS 抽取资产：每张 U8 表一个资产（组 u8_ods），可整组物化也可单表重跑。

底层复用 dm/connect/u8_mapping.sync（增量水位 + 审计留痕）；资产元数据带回抽取行数。
"""
from dagster import MaterializeResult, MetadataValue, asset

from dm.connect.u8_mapping import U8_TABLE_MAP, ods_name, sync


def _make_asset(mapping: dict):
    u8_table = mapping["u8"]

    @asset(
        name=ods_name(u8_table),
        group_name="u8_ods",
        description=f"U8 {mapping['cn']}（{u8_table}）→ StarRocks {ods_name(u8_table)}"
                    f"（游标 {mapping['cursor'] or '全量刷'}）",
        compute_kind="python",
    )
    def _u8_asset() -> MaterializeResult:
        rep = sync(tables=[u8_table], verbose=False)
        result = rep.get(u8_table)
        if not isinstance(result, int):
            raise RuntimeError(f"U8 抽取失败 {u8_table}: {result}")
        return MaterializeResult(metadata={
            "rows_pulled": result,
            "u8_table": u8_table,
            "cursor": MetadataValue.text(str(mapping["cursor"])),
        })

    return _u8_asset


u8_assets = [_make_asset(m) for m in U8_TABLE_MAP]
