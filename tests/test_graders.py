"""判分逻辑栈测试：实时执行 truth_sql，再用纯判分器比较答案。"""
import pytest

from dm.eval.run_eval import _grade, grade_refusal

SQL_QTY = "SELECT SUM(qty) FROM inventory WHERE material_id='M0001'"
SQL_WH = "SELECT DISTINCT warehouse_id FROM inventory WHERE material_id='M0001' ORDER BY 1"


def _numeric_case() -> dict[str, str]:
    return {"grader": "numeric", "truth_sql": SQL_QTY}


def _set_case() -> dict[str, str]:
    return {"grader": "set", "truth_sql": SQL_WH}


@pytest.mark.stack
def test_numeric_hit():
    assert _grade(_numeric_case(), "M0001 总库存 12 箱")[0] is True


@pytest.mark.stack
def test_numeric_no_false_hit():
    assert _grade(_numeric_case(), "总库存 120 箱")[0] is False


@pytest.mark.stack
def test_set_hit():
    assert _grade(_set_case(), "存放在 W02 半成品仓")[0] is True


@pytest.mark.stack
def test_set_missing():
    assert _grade(_set_case(), "存放在 W99 仓")[0] is False


def test_refusal_hit():
    assert grade_refusal("数据平台中暂无排班数据")[0] is True


def test_refusal_no_false():
    assert grade_refusal("库存是 12 箱")[0] is False
