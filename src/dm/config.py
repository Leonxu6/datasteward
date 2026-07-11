"""集中配置：数据/日志路径来自环境变量，与代码包解耦（便于部署）。

`DM_DATA_DIR` 指向存放运行时数据（`logs/`、嵌入缓存等）的目录；默认取当前工作目录，
因此在仓库根目录下运行时与历史行为一致。部署时设置 `DM_DATA_DIR` 即可把数据挪到包外。
"""
import glob
import os
import shutil
from pathlib import Path

DATA_DIR = Path(os.environ.get("DM_DATA_DIR") or Path.cwd()).resolve()
LOG_DIR = DATA_DIR / "logs"


def resolve_claude() -> str:
    """定位可执行的 claude CLI（智能体走无头 `claude -p`，需能被子进程启动）。

    解析顺序：
    1) 环境变量 `CLAUDE_BIN`（显式覆盖，最高优先）；
    2) PATH 上的 `claude`（标准/独立安装场景）；
    3) Windows 桌面版（MSIX 打包）兜底：真实文件在包的 LocalCache 下，
       `%APPDATA%\\Claude` 只是虚拟化视图、其他进程（如本 venv 的 Store Python）读不到，
       必须走 `%LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\...\\claude-code\\<版本>\\claude.exe`，
       并取最新安装的版本。

    都找不到则返回字面量 "claude"，交由上层在启动时报出清晰错误。
    """
    exe = os.environ.get("CLAUDE_BIN")
    if exe and os.access(exe, os.X_OK):
        return exe

    found = shutil.which("claude")
    if found:
        return found

    patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe"),
        os.path.expandvars(r"%APPDATA%\Claude\claude-code\*\claude.exe"),
    ]
    cands = []
    for pat in patterns:
        cands += [c for c in glob.glob(pat) if os.access(c, os.X_OK)]
    if cands:
        cands.sort(key=os.path.getmtime, reverse=True)  # 最新安装的版本优先
        return cands[0]

    return "claude"

# ---- 数据仓库：StarRocks（MySQL 协议）。S0 起替代 DuckDB ----
# 开发机经 SSH 隧道默认连本地转发端口（ssh -L 9030:127.0.0.1:9030 root@<host>）。
WH_HOST = os.environ.get("DM_WH_HOST", "127.0.0.1")
WH_PORT = int(os.environ.get("DM_WH_PORT", "9030"))
WH_USER = os.environ.get("DM_WH_USER", "root")          # 建库/灌数用
WH_PASSWORD = os.environ.get("DM_WH_PASSWORD", "")
WH_DB = os.environ.get("DM_WH_DB", "dm")
# 智能体只读查询连接（默认与 root 同，建好只读用户后切换为 dm_ro，做"连接级只读"双保险）
WH_RO_USER = os.environ.get("DM_WH_RO_USER", WH_USER)
WH_RO_PASSWORD = os.environ.get("DM_WH_RO_PASSWORD", WH_PASSWORD)
# dbt 产出层（DWD/DWS/ADS）所在库——与 transform/dbt 的 schema 同源，改这里须同步 DM_DW_SCHEMA
DW_SCHEMA = os.environ.get("DM_DW_SCHEMA", "dm_dw")

# ---- 影子源：Postgres（被 Flink CDC 的"假 ERP"）。S1 起 ----
# Flink 在主机内直连 5432；Windows 侧 seed/mutate 经 SSH 隧道连本地 15432→主机 5432。
SRC_PG_HOST = os.environ.get("DM_SRC_PG_HOST", "127.0.0.1")
SRC_PG_PORT = int(os.environ.get("DM_SRC_PG_PORT", "15432"))
SRC_PG_USER = os.environ.get("DM_SRC_PG_USER", "dm")
SRC_PG_PASSWORD = os.environ.get("DM_SRC_PG_PASSWORD", "dm_dev_pass")
SRC_PG_DB = os.environ.get("DM_SRC_PG_DB", "dm")

# ---- Flink REST（S1 管道健康视图用）。开发机经 SSH 隧道连本地 8081 ----
FLINK_REST = os.environ.get("DM_FLINK_REST", "http://127.0.0.1:8081")

# ---- 兼容别名：管理平台 UI（app/data.py）用 FLINK_URL / PG_* 命名，指向同一目标 ----
FLINK_URL = os.environ.get("DM_FLINK_URL", FLINK_REST)
PG_HOST = SRC_PG_HOST
PG_PORT = SRC_PG_PORT
PG_USER = SRC_PG_USER
PG_PASSWORD = SRC_PG_PASSWORD
PG_DB = SRC_PG_DB

# ---- 真实 ERP 源：用友 U8 / SQL Server（连接器框架用，可选）----
# 未配置时相关功能自动跳过；SQL Server 连接需 pyodbc 或 pymssql（可选依赖 `connectors` extra）。
# 凭据只从环境变量取，绝不写进代码/配置文件（对标 Palantir 凭据保管）。
SRC_MSSQL_HOST = os.environ.get("DM_SRC_MSSQL_HOST", "")
SRC_MSSQL_PORT = int(os.environ.get("DM_SRC_MSSQL_PORT", "1433"))
SRC_MSSQL_USER = os.environ.get("DM_SRC_MSSQL_USER", "")
SRC_MSSQL_PASSWORD = os.environ.get("DM_SRC_MSSQL_PASSWORD", "")
SRC_MSSQL_DB = os.environ.get("DM_SRC_MSSQL_DB", "")

# ---- 文件连接器落地目录（CSV/Excel，接 MES 导出 / 线下表）----
FILE_SOURCE_DIR = Path(os.environ.get("DM_FILE_SOURCE_DIR") or (DATA_DIR / "file_sources"))

# ---- LLM（L10）：LangGraph 智能体 / eval LLM-judge / KG 文档抽取共用一个 OpenAI 兼容端点 ----
# 任意 OpenAI 兼容端点皆可：云端 API（OpenAI/DeepSeek/Moonshot…）或本地 ollama/LiteLLM 网关
# （数据不出域）。默认指向本地 ollama；云端用法见根目录 .env.example。
# api_key 对本地网关无鉴权要求，占位即可。
LLM_BASE_URL = os.environ.get("DM_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_API_KEY = os.environ.get("DM_LLM_API_KEY", "sk-local")
LLM_MODEL = os.environ.get("DM_LLM_MODEL", "qwen3:8b")

# ---- LLM 流式与分层超时（僵尸根治，DEVLOG 坑27）----
# 非流式请求在客户端死亡后不会取消：孤儿请求在推理后端空转、占死并发槽。全链路改流式后，
# 任何一环断开→写失败→ollama 当场中止生成释放槽位。此开关仅作流式聚合出回归时的应急回退。
LLM_STREAMING = os.environ.get("DM_LLM_STREAMING", "1").lower() not in ("0", "false", "no")
LLM_CONNECT_TIMEOUT = float(os.environ.get("DM_LLM_CONNECT_TIMEOUT", "10"))
LLM_READ_TIMEOUT = float(os.environ.get("DM_LLM_READ_TIMEOUT", "60"))    # 流式下=相邻 token 间隔上限
LLM_WALL_TIMEOUT = float(os.environ.get("DM_LLM_WALL_TIMEOUT", "240"))   # 单次 LLM 调用墙钟上限
# 单次调用生成 token 上限：思考型模型遇开放分析题会失控长写（实测单步 4 分钟撞墙钟），
# 从供给侧掐断；thinking 吃满上限导致终答为空时有"塌缩兜底"再要一次收尾。
LLM_MAX_TOKENS = int(os.environ.get("DM_LLM_MAX_TOKENS", "4096"))

# ---- 演示数据日期锚（仅合成数据环境设置，如 "2026-06-25"）----
# 合成数据的"今天"冻结在造数锚（generate.py TODAY / dbt anchor_today），而系统墙钟持续漂移，
# 模型用 CURRENT_DATE() 解释"今天/明天/上月"会得到荒诞结论（如"明天的发货已签收"）。
# 设置后注入 SYSTEM，让相对时间以数据锚为准；接真库（U8 真实数据）时留空即回归墙钟。
ANCHOR_TODAY = os.environ.get("DM_ANCHOR_TODAY", "").strip()

# ---- LangGraph 检查点库：复用同一 Postgres（表由 langgraph 自动建）；不可达时智能体自动降级内存检查点 ----
CKPT_PG_URL = os.environ.get(
    "DM_CKPT_PG_URL",
    f"postgresql://{os.environ.get('DM_SRC_PG_USER', 'dm')}:{os.environ.get('DM_SRC_PG_PASSWORD', 'dm_dev_pass')}"
    f"@{os.environ.get('DM_SRC_PG_HOST', '127.0.0.1')}:{os.environ.get('DM_SRC_PG_PORT', '15432')}"
    f"/{os.environ.get('DM_SRC_PG_DB', 'dm')}",
)

# ---- Neo4j 知识图谱（S3）。默认连本地 7687（bolt）；密码与 deploy/docker-compose.yml 对应 ----
NEO4J_URI = os.environ.get("DM_NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.environ.get("DM_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("DM_NEO4J_PASSWORD", "datasteward-dev")
