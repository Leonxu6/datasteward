"""判分逻辑单测（确定性，不调用智能体）。

numeric/set 判分器要对仓库实时执行 truth_sql 算真值 → 标 stack；refusal 是纯文本判定。
"""
import pytest

from dm.eval.run_eval import grade_numeric, grade_set, grade_refusal

SQL_QTY = "SELECT SUM(qty) FROM inventory WHERE material_id='M0001'"
SQL_WH = "SELECT DISTINCT warehouse_id FROM inventory WHERE material_id='M0001' ORDER BY 1"


@pytest.mark.stack
def test_numeric_hit():
    assert grade_numeric(SQL_QTY, "M0001 总库存 12 箱")[0] is True


@pytest.mark.stack
def test_numeric_no_false_hit():
    assert grade_numeric(SQL_QTY, "总库存 120 箱")[0] is False


@pytest.mark.stack
def test_set_hit():
    assert grade_set(SQL_WH, "存放在 W02 半成品仓")[0] is True


@pytest.mark.stack
def test_set_missing():
    assert grade_set(SQL_WH, "存放在 W99 仓")[0] is False


def test_refusal_hit():
    assert grade_refusal("数据平台中暂无排班数据")[0] is True


def test_refusal_no_false():
    assert grade_refusal("库存是 12 箱")[0] is False
