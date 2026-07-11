"""图查询子进程入口：供 connector/mcp_server.py 的 graph_query 在**干净子进程**里跑。

理由同 docs/search_cli.py：把第三方驱动隔离出 stdio-MCP 的 asyncio 运行时，避免污染 JSON-RPC 通道。
约定：结果 JSON 以单行 `DMJSON:` 前缀打到 stdout，其余日志走 stderr。
用法：python -m dm.kg.graph_cli <mode> '<json-args>'
"""
import json
import sys


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "find_related"
    try:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    except Exception:  # noqa: BLE001
        args = {}
    from dm.kg.query import find_related, impact_path, restricted_cypher
    if mode == "find_related":
        res = find_related(args.get("entity_id", ""), args.get("max_hops", 2), args.get("limit", 30))
    elif mode == "impact_path":
        res = impact_path(args.get("entity_id", ""), args.get("target_type", ""),
                          args.get("max_hops", 4), args.get("limit", 20))
    elif mode == "cypher":
        res = restricted_cypher(args.get("cypher", ""), args.get("limit", 50))
    else:
        res = {"error": f"未知 mode: {mode}（可用 find_related / impact_path / cypher）"}
    sys.stdout.write("DMJSON:" + json.dumps(res, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
