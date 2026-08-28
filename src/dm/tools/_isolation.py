"""子进程隔离助手：在干净子进程里跑原生库重的检索/图查询（DMJSON 协议）。

为什么存在（DEVLOG 坑11）：onnxruntime / psycopg2 等原生库会污染宿主进程的 stdio，
在 stdio-MCP 形态下曾把 JSON-RPC 通道搞崩。治理内核保留子进程隔离：
- 同步版 run_isolated：给进程内 LangGraph 智能体用（无 stdio 通道之忧，但仍隔离崩溃面）；
- 异步版 arun_isolated：给 FastMCP（asyncio）壳用——Windows proactor 循环里必须用
  async 子进程 + stdin=DEVNULL，否则与管道争用死锁（实测结论，勿改）。

协议：子模块把结果以单行 `DMJSON:<json>` 打到 stdout，其余输出一律当日志忽略。
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def _sub_env() -> dict:
    """子进程环境：UTF-8 + 嵌入缓存显式注入 + HF 离线（防联网卡死）。"""
    return {
        **os.environ,
        "PYTHONUTF8": "1",
        "DM_EMBED_CACHE": os.environ.get("DM_EMBED_CACHE", str(Path.home() / ".cache" / "dm_fastembed")),
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"),
        "HF_HUB_DISABLE_SYMLINKS": "1",
    }


def _parse_dmjson(out: str, err: str):
    line = next((ln for ln in out.splitlines() if ln.startswith("DMJSON:")), None)
    if line is None:
        raise RuntimeError((err or out or "无输出").strip()[-300:])
    return json.loads(line[len("DMJSON:"):])


def run_isolated(module: str, argv: list, timeout: int):
    """同步跑 `python -m <module> <argv...>`，解析 DMJSON 结果；超时/无结果抛 RuntimeError。"""
    try:
        p = subprocess.run(
            [sys.executable, "-m", module, *argv],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=_sub_env(), timeout=timeout,
            check=False,  # DMJSON is the protocol outcome; non-zero exit is interpreted below.
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"子进程超时（{timeout}s）: {module}") from None
    return _parse_dmjson(p.stdout or "", p.stderr or "")


async def arun_isolated(module: str, argv: list, timeout: int):
    """异步版（FastMCP/asyncio 场景专用）。stdin 必须 DEVNULL——见模块 docstring。"""
    import asyncio
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", module, *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=_sub_env())
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"子进程超时（{timeout}s）: {module}") from None
    return _parse_dmjson(out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace"))
