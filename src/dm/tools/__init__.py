"""治理内核：8 个受治理工具 + PBAC + 审计 + 脱敏，一处实现、多端消费。

消费方：
- 进程内：LangGraph 智能体（dm/agent/graph.py）直接调用同步函数，显式传 Principal；
- 对外：stdio MCP 壳（dm/connector/mcp_server.py）薄委托，Principal 来自环境变量注入。

两条路径的权限判定、审计字段、报错文案完全一致——治理逻辑只此一份。
"""
from dm.tools.actions_tool import execute_action
from dm.tools.data import MAX_ROWS, describe_table, list_tables, run_sql
from dm.tools.documents import asearch_documents, search_documents
from dm.tools.graph import agraph_query, graph_query
from dm.tools.metrics_tool import list_metrics, query_metric
from dm.tools.principal import Principal, principal_from_env

__all__ = [
    "MAX_ROWS", "Principal", "principal_from_env",
    "list_tables", "describe_table", "run_sql",
    "search_documents", "asearch_documents",
    "graph_query", "agraph_query",
    "execute_action",
    "query_metric", "list_metrics",
]
