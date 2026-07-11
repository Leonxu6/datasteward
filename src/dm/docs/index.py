"""文档索引（S2）：解析 → 切片 → 本地嵌入 → 写入 pgvector 的 doc_chunk。

按 content-hash 增量重建：仅对内容变化（或未索引）的文档重切片重嵌入，其余跳过——
对应"重同步：content-hash 变 → 重切片重嵌入"。整体是分钟级离线作业。

CLI（dm-docs）：
  dm-docs build            合成文档 + 索引（首次一键就绪）
  dm-docs gen              仅（重新）合成文档并注册（不嵌入）
  dm-docs index            仅索引 content-hash 变化的文档（增量）
  dm-docs reindex          强制全量重索引
  dm-docs status           文档/切片数与各文档索引状态
  dm-docs search "<query>" 命令行试检索（调试用）
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from dm.docs.embed import embed
from dm.docs.store import connect, connect_vec, counts, init_schema


def chunk_text(text, target=380, overlap=80):
    """中文友好切片：先按段落切，合并到 target 长度；超长段落滑窗切（带 overlap）。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 1 <= target:
            buf = (buf + "\n" + p).strip()
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(p) <= target:
            buf = p
        else:
            i = 0
            while i < len(p):
                chunks.append(p[i:i + target])
                i += target - overlap
    if buf:
        chunks.append(buf)
    return chunks or [text.strip()]


def reindex(force=False, verbose=True):
    """对 content-hash 变化（或 force）的文档重切片重嵌入，写入 doc_chunk。"""
    init_schema()
    meta = connect()              # 读注册表 + 更新状态
    mcur = meta.cursor()
    vec = connect_vec()           # 写向量（注册 pgvector 适配）
    vcur = vec.cursor()
    mcur.execute("SELECT doc_id, doc_type, title, entities, source_path, content_hash, indexed_hash "
                 "FROM document ORDER BY doc_id")
    rows = mcur.fetchall()
    n_doc = n_chunk = skipped = 0
    for doc_id, dtype, title, entities, path, chash, ihash in rows:
        if not force and chash is not None and chash == ihash:
            skipped += 1
            continue
        body = Path(path).read_text(encoding="utf-8")
        chunks = chunk_text(body)
        embs = embed(chunks)      # 批量嵌入（文档侧）
        vcur.execute("DELETE FROM doc_chunk WHERE doc_id=%s", (doc_id,))
        recs = [(f"{doc_id}-{i:03d}", doc_id, dtype, title, entities, i, ch,
                 np.asarray(e, dtype="float32"))
                for i, (ch, e) in enumerate(zip(chunks, embs))]
        vcur.executemany(
            "INSERT INTO doc_chunk(chunk_id,doc_id,doc_type,title,entities,chunk_no,content,embedding) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", recs)
        mcur.execute("UPDATE document SET indexed_hash=%s, n_chunks=%s, indexed_at=%s WHERE doc_id=%s",
                     (chash, len(chunks), datetime.now(), doc_id))
        n_doc += 1
        n_chunk += len(chunks)
        if verbose:
            print(f"  索引 {doc_id} «{title[:24]}» → {len(chunks)} 片")
    vec.close()
    meta.close()
    nd, nc = counts()
    if verbose:
        print(f"=== 重索引 {n_doc} 篇（{n_chunk} 片），跳过未变 {skipped} 篇；"
              f"现库内共 {nd} 篇 / {nc} 片 ===")
    return n_doc, n_chunk


def status():
    nd, nc = counts()
    print(f"=== 文档知识库：{nd} 篇 / {nc} 片（pgvector）===")
    c = connect()
    cur = c.cursor()
    cur.execute("SELECT doc_id, doc_type, n_chunks, entities, "
                "CASE WHEN content_hash=indexed_hash THEN '已索引' ELSE '待索引' END, title "
                "FROM document ORDER BY doc_id")
    for doc_id, dtype, n, ent, st, title in cur.fetchall():
        print(f"  {doc_id}  {dtype:9} {st}  {n} 片  [{ent}]  {title}")
    c.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    cmd = args[0] if args else "build"
    if cmd == "build":
        from dm.docs.generate_docs import gen
        docs = gen()
        print(f"已合成并注册 {len(docs)} 篇文档，开始索引…")
        reindex(force=False)
    elif cmd == "gen":
        from dm.docs.generate_docs import main as gmain
        gmain()
    elif cmd == "index":
        reindex(force=False)
    elif cmd == "reindex":
        reindex(force=True)
    elif cmd == "status":
        status()
    elif cmd == "search":
        from dm.docs.search import search
        q = " ".join(args[1:]) or "逾期交货违约金"
        for h in search(q, top_k=5):
            print(f"  [{h['score']:.3f}] {h['doc_id']} {h['doc_type']} «{h['title'][:24]}» "
                  f"[{h['entities']}]\n      {h['content'][:80].strip()}…")
    else:
        print(f"未知命令 {cmd}。可用：build / gen / index / reindex / status / search")


if __name__ == "__main__":
    main()
