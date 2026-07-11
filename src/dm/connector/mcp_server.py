"""MCP 连接器（薄壳）：把治理内核 dm/tools 以标准 stdio MCP 暴露给外部客户端。

自研 LangGraph 智能体在进程内直调治理内核，不经过本服务器；本壳供**外部** MCP 客户端
（桌面助手 / IDE / 其它智能体）接入同一套受治理工具——工具名、参数、
返回格式、PBAC/审计行为与进程内路径完全一致（治理逻辑只在 dm/tools 一份）。

工具：list_tables / describe_table / run_sql / search_documents / graph_query / execute_action
身份：经环境变量注入（DM_SESSION_ID / DM_CHANNEL / DM_USER / DM_ROLE / DM_PURPOSE），
      与旧版契约一致；每次调用留痕 logs/audit_log.jsonl。

运行（由外部客户端作为 stdio 子进程拉起）：
  python -m dm.connector.mcp_server
"""
from mcp.server.fastmcp import FastMCP

from dm import tools as kernel
from dm.tools import principal_from_env

mcp = FastMCP("dm")

_P = principal_from_env()


@mcp.tool()
def list_tables() -> str:
    """列出数据仓库里所有业务表（表英文名、中文名、说明、行数）。建议先调用它了解有哪些数据。"""
    return kernel.list_tables(_P)


@mcp.tool()
def describe_table(name: str) -> str:
    """查看某张表的字段定义：列名、类型、中文名、是否主键、外键指向。参数 name 为表英文名。"""
    return kernel.describe_table(_P, name)


@mcp.tool()
def run_sql(sql: str) -> str:
    """对数据仓库执行只读 SELECT 查询并返回结果（最多 200 行，JSON）。
    仅允许单条 SELECT / WITH 查询；任何写操作、DDL、多语句都会被拒绝。
    表结构请先用 list_tables / describe_table 获取。"""
    return kernel.run_sql(_P, sql)


@mcp.tool()
async def search_documents(query: str, top_k: int = 5) -> str:
    """检索非结构化文档库（采购合同 / 作业指导书SOP / 进货检验质检报告 / 设备维护手册 / 物料技术规格书）。
    当问题涉及『文档里才有』的内容时用它做语义检索，例如：合同条款（账期/违约金/质保）、
    工艺与作业 SOP（工序/公差/关键设备）、设备维护周期与报警码、质检结论与不良率、物料技术规格（材质/存储/保质期）。
    参数：query 自然语言问题（可含物料/供应商/到货等 ID 以精确定位）；top_k 返回片段数（默认 5）。
    返回 JSON 数组，每条含 doc_id / doc_type / title / entities(关联实体ID) / chunk_no / score / content。
    请据返回片段作答并标注出处（文档标题或 doc_id）；若片段中查不到答案，如实说明『文档未提及』，不要臆造。"""
    return await kernel.asearch_documents(_P, query, top_k)


@mcp.tool()
async def graph_query(mode: str, entity_id: str = "", target_type: str = "",
                      max_hops: int = 3, cypher: str = "", limit: int = 30) -> str:
    """知识图谱查询（实体关系层 = 结构化外键骨架 + 文档抽取的新关系，存于 Neo4j）。三种 mode：
    - find_related：找与 entity_id（如供应商 S001 / 物料 M0001 / 设备 CNC-08）max_hops 跳内相连的实体与关系——跨域链接发现。
    - impact_path：从 entity_id 到 target_type（如 Customer / SalesOrder / Material / Document）的最短路径——断供影响 / 质量溯源等多跳分析。
    - cypher：执行只读 Cypher（高级；写/管理操作被拒）。
    何时用：问『谁会被牵连/影响』『经由哪些环节关联』『上下游链路』『跨结构化+文档的关系』等图式问题。
    返回 JSON（find_related→related[]；impact_path→paths[]含 path 节点链；cypher→rows[]）。常与 run_sql / search_documents 组合作答。"""
    return await kernel.agraph_query(_P, mode, entity_id, target_type, max_hops, cypher, limit)


@mcp.tool()
def list_metrics() -> str:
    """列出全部业务指标定义（名称/中文名/口径说明/允许维度/单位/负责人）。回答口径类问题先看这里。"""
    return kernel.list_metrics(_P)


@mcp.tool()
def query_metric(metric: str, dimensions: str = "", filters: str = "", limit: int = 100) -> str:
    """按注册口径查询业务指标数值（缺料物料数/净需求/可发货量/库存总量/采购在途量/销售额）。
    参数：metric 指标名（先用 list_metrics 查可用项）；dimensions 逗号分隔的分组维度（可空）；
    filters 分号分隔的过滤（形如 material_id='M0001'；只接受简单比较）；limit 行数上限。
    返回 JSON：{metric, cn, sql, columns, rows}。涉敏指标受 Marking/PBAC 约束，无权会被拒。"""
    return kernel.query_metric(_P, metric, dimensions, filters, limit)


@mcp.tool()
def execute_action(action: str, material_id: str = "", new_value: int = 0,
                   supplier_id: str = "", qty: int = 0, so_id: str = "",
                   approve: bool = False) -> str:
    """执行一次**治理化写回 Action**（会改源系统数据，受写回权限约束、全程留审计、可回滚）。支持：
    - adjust_safety_stock(material_id, new_value)：调整物料安全库存阈值
    - create_purchase_requisition(material_id, supplier_id, qty)：生成采购申请
    - create_delivery(so_id, qty)：发起发货（**提交条件：现有库存≥qty**，不足会被拒）
    默认 approve=False 只返回『待审批预览』(不写库)；需人工在审批台批准、或明确 approve=True 才真正写回。
    仅当用户明确要求执行上述写操作时使用；只读查询一律用 run_sql。
    返回 JSON：ok / status(pending_approval) / preview / message / error。权限不足或提交条件不满足会被拒。"""
    return kernel.execute_action(_P, action, material_id, new_value, supplier_id, qty, so_id, approve)


if __name__ == "__main__":
    mcp.run()
