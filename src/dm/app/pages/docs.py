"""📚 文档知识库（RAG）：合成实体挂钩文档 → 本地嵌入 bge → pgvector。

与智能体 `search_documents` 工具**同一检索路径**：展示文档注册表 + 向量切片数 + 实时混合检索命中与出处。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import components as C


def render():
    try:
        from dm.docs import store as docstore
        from dm.docs.search import search as doc_search
    except Exception as e:  # noqa: BLE001
        C.banner(f"RAG 模块不可用：{str(e)[:120]}（需 pip install -e .[rag]）")
        return
    try:
        nd, nc = docstore.counts()
    except Exception as e:  # noqa: BLE001
        C.banner(f"向量库不可达：{str(e)[:120]}（确认隧道转发 15432 且已 dm-docs build）")
        return

    t_search, t_reg = st.tabs(["语义检索", "文档注册表"])

    with t_reg:
        C.kpi_row([
            ("文档数", nd, "", "info"),
            ("向量切片", nc, "", "info"),
            ("嵌入模型", "bge-small-zh", "", "info"),
        ], min_w=150)
        try:
            con = docstore.connect()
            cur = con.cursor()
            cur.execute("SELECT doc_id, doc_type, title, entities, n_chunks, "
                        "CASE WHEN content_hash=indexed_hash THEN '✅' ELSE '⏳' END, indexed_at "
                        "FROM document ORDER BY doc_id")
            rows = cur.fetchall()
            con.close()
        except Exception as e:  # noqa: BLE001
            C.banner(f"读取注册表失败：{str(e)[:120]}")
            return
        with C.card("文档注册表", "合成文档引用真实物料/供应商/订单/到货/设备 ID，可与数仓跨域链接"):
            df = pd.DataFrame(rows, columns=["doc_id", "类型", "标题", "关联实体", "切片", "索引", "索引时间"])
            st.dataframe(df, use_container_width=True, hide_index=True, height=420)

    with t_search:
        st.caption("混合检索：bge 向量 + 实体词法加权（查询里的 S001/M0001/PA0001/CNC-08 命中文档关联实体则加权），与智能体工具一致。")
        examples = ["供应商 S001 合同的逾期违约金和质保期", "物料 M0001 精加工公差要求",
                    "CNC-08 多久更换主轴润滑油", "采购到货 PA0001 质检不良率与结论"]
        if "doc_q" not in st.session_state:
            st.session_state.doc_q = ""
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            if cols[i].button(f"示例{i + 1}", help=ex, key=f"dex{i}"):
                st.session_state.doc_q = ex
        q = st.text_input("检索文档", value=st.session_state.doc_q,
                          placeholder="例：供应商 S001 合同的违约金是怎么约定的？")
        if st.button("检索", type="primary") and q.strip():
            try:
                hits = doc_search(q.strip(), top_k=5)
            except Exception as e:  # noqa: BLE001
                C.banner(f"检索失败：{str(e)[:120]}")
                return
            C.kpi_row([
                ("命中片段", len(hits), "", "ok" if hits else "muted"),
                ("最高混合分", f'{hits[0]["score"]:.3f}' if hits else "—", "", "info"),
            ], min_w=150)
            for h in hits:
                with C.card(f'{h["doc_id"]} · {h["doc_type"]} · {h["title"]}',
                            f'关联实体 {h["entities"]}　|　混合分 {h["score"]:.3f}（向量 {h["vscore"]:.3f}）· 片段 #{h["chunk_no"]}'):
                    st.code(h["content"], language="text")
