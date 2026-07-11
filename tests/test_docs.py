"""文档 RAG 单测（确定性）：切片 / 嵌入接口 / 实体抽取 / 文档锚点事实 / contains 判分。

不下载嵌入模型、不连向量库——用 hash 后端 + 纯函数校验。检索质量与端到端走 dm-docs / dm-eval 实跑。
"""
import os

os.environ["DM_EMBED_BACKEND"] = "hash"  # 切到无依赖的确定性后端，避免下载模型

from dm.docs.embed import DIM, embed_one  # noqa: E402
from dm.docs.generate_docs import build_documents  # noqa: E402
from dm.docs.index import chunk_text  # noqa: E402
from dm.docs.search import _entities  # noqa: E402
from dm.eval.run_eval import grade_contains  # noqa: E402
from dm.warehouse.generate import build_all  # noqa: E402


def test_chunk_text_nonempty_and_bounded():
    txt = "第一段较短。\n\n第二段。\n\n" + "啊" * 500
    chunks = chunk_text(txt, target=380, overlap=80)
    assert chunks and all(c.strip() for c in chunks)
    assert all(len(c) <= 380 for c in chunks)  # 超长段已滑窗切到上限内


def test_embed_hash_dim_and_deterministic():
    a = embed_one("逾期违约金 0.5% 封顶 5%")
    b = embed_one("逾期违约金 0.5% 封顶 5%")
    assert len(a) == DIM and a == b


def test_entities_extract():
    ents = _entities("供应商 S001 的 M0001 与到货 PA0001 用设备 CNC-08")
    assert {"S001", "M0001", "PA0001", "CNC-08"} <= ents


def test_build_documents_anchor_facts():
    """eval 真值依赖的锚点事实必须确实写在对应文档正文里。"""
    body = {x["doc_id"]: x["body"] for x in build_documents()}
    assert "0.5%" in body["DOC0001"] and "12 个月" in body["DOC0001"]
    assert "0.02mm" in body["DOC0004"]
    assert "500 小时" in body["DOC0009"]
    assert "6.25%" in body["DOC0006"] and "让步接收" in body["DOC0006"]
    assert "24 个月" in body["DOC0011"]


def test_documents_reference_real_entities():
    """文档关联的物料/供应商 ID 必须真实存在（与数仓同一批实体，保证可跨域链接）。"""
    data = build_all()
    mids = {m["material_id"] for m in data["material"]}
    sids = {s["supplier_id"] for s in data["supplier"]}
    for doc in build_documents():
        for e in doc["entities"]:
            if len(e) >= 2 and e[0] == "M" and e[1:].isdigit():
                assert e in mids, f'{doc["doc_id"]} 引用了不存在的物料 {e}'
            if len(e) >= 2 and e[0] == "S" and e[1:].isdigit():
                assert e in sids, f'{doc["doc_id"]} 引用了不存在的供应商 {e}'


def test_grade_contains():
    assert grade_contains(["0.5%", "12个月"], "逾期每日 0.5%，质保 12 个月")[0] is True
    assert grade_contains(["0.5%", "12个月"], "逾期每日 0.5%（未提质保）")[0] is False
