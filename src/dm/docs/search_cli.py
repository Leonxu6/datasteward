"""文档检索子进程入口：给 connector/mcp_server.py 的 search_documents 在**干净子进程**里跑检索。

为什么要子进程：MCP 是 stdio 服务器（stdout 即 JSON-RPC 通道）。在其 asyncio 运行时里直接跑
嵌入模型(onnxruntime, C++ 写 fd1) / psycopg2 等原生库，会污染/打断 stdout 的 JSON-RPC（实测
BrokenResourceError → claude 卡死）。隔离到子进程后：原生库的输出留在子进程，主服务器 stdout 纯净。
约定：仅把结果 JSON 以 `DMJSON:` 前缀单行打到 stdout，其余（模型日志等）都在 stderr，调用方按前缀取。
用法：python -m dm.docs.search_cli "<query>" <top_k>
"""
import json
import sys


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    except ValueError:
        top_k = 5
    from dm.docs.search import search
    hits = search(query, top_k=top_k)
    sys.stdout.write("DMJSON:" + json.dumps(hits, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
