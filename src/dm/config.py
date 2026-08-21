"""集中配置：运行时路径、服务端点和连接参数来自环境变量。

高风险数值和 URL 通过严格解析器在进程启动时失败，避免非法端口、NaN 超时、拼错的
布尔值或缺主机名 URL 一直传播到数据库/LLM/Flink 客户端后才以模糊异常失败。
"""
import glob
import os
import shutil
from pathlib import Path

from dm.config_validation import env_bool, env_float, env_http_url, env_int, env_text

_raw_data_dir = os.environ.get("DM_DATA_DIR")
DATA_DIR = Path(_raw_data_dir or Path.cwd()).expanduser().resolve()
LOG_DIR = DATA_DIR / "logs"


def resolve_claude() -> str:
    """定位可执行的 claude CLI；找不到时返回字面量 ``claude`` 交由上层报错。"""
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
    candidates = []
    for pattern in patterns:
        candidates += [candidate for candidate in glob.glob(pattern) if os.access(candidate, os.X_OK)]
    if candidates:
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]
    return "claude"


# ---- 数据仓库：StarRocks（MySQL 协议） ----
WH_HOST = env_text("DM_WH_HOST", "127.0.0.1")
WH_PORT = env_int("DM_WH_PORT", 9030, minimum=1, maximum=65535)
WH_USER = env_text("DM_WH_USER", "root")
WH_PASSWORD = env_text("DM_WH_PASSWORD", "", allow_empty=True, max_length=1000)
WH_DB = env_text("DM_WH_DB", "dm")
WH_RO_USER = env_text("DM_WH_RO_USER", WH_USER)
WH_RO_PASSWORD = env_text("DM_WH_RO_PASSWORD", WH_PASSWORD, allow_empty=True, max_length=1000)
DW_SCHEMA = env_text("DM_DW_SCHEMA", "dm_dw")

# ---- 影子源：PostgreSQL ----
SRC_PG_HOST = env_text("DM_SRC_PG_HOST", "127.0.0.1")
SRC_PG_PORT = env_int("DM_SRC_PG_PORT", 15432, minimum=1, maximum=65535)
SRC_PG_USER = env_text("DM_SRC_PG_USER", "dm")
SRC_PG_PASSWORD = env_text("DM_SRC_PG_PASSWORD", "dm_dev_pass", allow_empty=True, max_length=1000)
SRC_PG_DB = env_text("DM_SRC_PG_DB", "dm")

# ---- Flink REST ----
FLINK_REST = env_http_url("DM_FLINK_REST", "http://127.0.0.1:8081")
FLINK_URL = env_http_url("DM_FLINK_URL", FLINK_REST)
PG_HOST = SRC_PG_HOST
PG_PORT = SRC_PG_PORT
PG_USER = SRC_PG_USER
PG_PASSWORD = SRC_PG_PASSWORD
PG_DB = SRC_PG_DB

# ---- 真实 ERP 源：用友 U8 / SQL Server（可选） ----
SRC_MSSQL_HOST = env_text("DM_SRC_MSSQL_HOST", "", allow_empty=True)
SRC_MSSQL_PORT = env_int("DM_SRC_MSSQL_PORT", 1433, minimum=1, maximum=65535)
SRC_MSSQL_USER = env_text("DM_SRC_MSSQL_USER", "", allow_empty=True)
SRC_MSSQL_PASSWORD = env_text("DM_SRC_MSSQL_PASSWORD", "", allow_empty=True, max_length=1000)
SRC_MSSQL_DB = env_text("DM_SRC_MSSQL_DB", "", allow_empty=True)

# ---- 文件连接器 ----
FILE_SOURCE_DIR = Path(os.environ.get("DM_FILE_SOURCE_DIR") or (DATA_DIR / "file_sources")).expanduser()

# ---- LLM ----
LLM_BASE_URL = env_http_url("DM_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LLM_API_KEY = env_text("DM_LLM_API_KEY", "sk-local", allow_empty=True, max_length=4096)
LLM_MODEL = env_text("DM_LLM_MODEL", "qwen3:8b", max_length=200)
LLM_STREAMING = env_bool("DM_LLM_STREAMING", True)
LLM_CONNECT_TIMEOUT = env_float("DM_LLM_CONNECT_TIMEOUT", 10, minimum=0.1, maximum=3600)
LLM_READ_TIMEOUT = env_float("DM_LLM_READ_TIMEOUT", 60, minimum=0.1, maximum=3600)
LLM_WALL_TIMEOUT = env_float("DM_LLM_WALL_TIMEOUT", 240, minimum=0.1, maximum=86400)
LLM_MAX_TOKENS = env_int("DM_LLM_MAX_TOKENS", 4096, minimum=1, maximum=131072)

# ---- 演示数据日期锚 ----
ANCHOR_TODAY = os.environ.get("DM_ANCHOR_TODAY", "").strip()

# ---- LangGraph 检查点 ----
CKPT_PG_URL = os.environ.get(
    "DM_CKPT_PG_URL",
    f"postgresql://{SRC_PG_USER}:{SRC_PG_PASSWORD}@{SRC_PG_HOST}:{SRC_PG_PORT}/{SRC_PG_DB}",
)

# ---- Neo4j 知识图谱 ----
NEO4J_URI = os.environ.get("DM_NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = env_text("DM_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = env_text("DM_NEO4J_PASSWORD", "datasteward-dev", allow_empty=True, max_length=1000)
