"""冒烟测试：仓库可查 + 外键完整性（确定性，SEED=42）。"""

import pytest

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过
from dm.warehouse.store import connect_ro


def test_warehouse_queryable_and_fk_integrity():
    con = connect_ro()
    try:
        # 稳定 ID：M0001 总库存 12 @ W02
        assert con.execute(
            "SELECT SUM(qty) FROM inventory WHERE material_id='M0001'").fetchone()[0] == 12
        whs = [r[0] for r in con.execute(
            "SELECT DISTINCT warehouse_id FROM inventory WHERE material_id='M0001'").fetchall()]
        assert "W02" in whs
        # 物料主数据 50 条
        assert con.execute("SELECT COUNT(*) FROM material").fetchone()[0] == 50
        # 外键完整性：库存指向不存在物料的行应为 0
        # 显式 ON（勿用 USING：新版 StarRocks 里 USING 合并列不可再用右表别名限定）
        orphans = con.execute(
            "SELECT COUNT(*) FROM inventory i LEFT JOIN material m ON i.material_id = m.material_id "
            "WHERE m.material_id IS NULL").fetchone()[0]
        assert orphans == 0
    finally:
        con.close()
