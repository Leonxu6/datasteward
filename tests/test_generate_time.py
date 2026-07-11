"""合成数据时间一致性单测。

背景：发货单/到货单状态曾纯随机，出现"delivery_date=2026-07-09 已签收"这类穿越数据，
智能体如实转述后产生"明天的发货已完成"荒诞答案。修复=未来日期事后矫正状态，
且 rng 调用序不变——稳定测试 ID（CONTRIBUTING.md 数据须知：M0001/SO0001/S001）与 eval 真值依赖同一随机流。
"""
from dm.warehouse.generate import TODAY, build_all


def _data():
    # build_all 确定性（固定 SEED+TODAY），模块内缓存一份即可
    global _CACHE
    try:
        return _CACHE
    except NameError:
        _CACHE = build_all()
        return _CACHE


def test_future_delivery_never_shipped_or_signed():
    for r in _data()["delivery_note"]:
        if r["delivery_date"] > TODAY:
            assert r["status"] == "待发", f'{r["delivery_id"]} {r["delivery_date"]} 竟为 {r["status"]}'


def test_future_arrival_never_inspected_or_stocked():
    for r in _data()["purchase_arrival"]:
        if r["arrival_date"] > TODAY:
            assert r["status"] == "待检", f'{r["arrival_id"]} {r["arrival_date"]} 竟为 {r["status"]}'


def test_past_rows_keep_variety():
    # 修复只允许矫正未来行；历史行应保留原随机多样性（防止把整表改成单一状态）
    past = {r["status"] for r in _data()["delivery_note"] if r["delivery_date"] <= TODAY}
    assert len(past) >= 2


def test_rng_stream_unchanged_stable_ids():
    """随机流金丝雀：冻结契约的稳定测试 ID 必须原样成立（CONTRIBUTING.md 数据须知）。"""
    data = _data()
    m1 = sum(r["qty"] for r in data["inventory"]
             if r["material_id"] == "M0001" and r["warehouse_id"] == "W02")
    assert m1 == 12, f"M0001@W02 库存漂移: {m1}"
    so1 = [r for r in data["sales_order"] if r["so_id"] == "SO0001"]
    assert [(r["material_id"], r["qty"]) for r in so1] == [("M0046", 265)], "SO0001 行漂移"
    po21 = {r["supplier_id"] for r in data["purchase_order"] if r["po_id"] == "PO0021"}
    assert po21 == {"S001"}, f"PO0021 供应商漂移: {po21}"
