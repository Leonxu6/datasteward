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

_MAX_TIMEOUT_SECONDS = 600
_MAX_PROTOCOL_LINE_CHARS = 1_000_000
_DMJSON_PREFIX = "DMJSON:"


def _timeout_seconds(timeout: object) -> int:
    """Validate one bounded subprocess timeout before any process is created."""
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise ValueError("isolation timeout must be an integer")
    if timeout < 1 or timeout > _MAX_TIMEOUT_SECONDS:
        raise ValueError(f"isolation timeout must be between 1 and {_MAX_TIMEOUT_SECONDS} seconds")
    return timeout


def _sub_env() -> dict:
    """子进程环境：UTF-8 + 嵌入缓存显式注入 + HF 离线（防联网卡死）。"""
    return {
        **os.environ,
        "PYTHONUTF8": "1",
        "DM_EMBED_CACHE": os.environ.get("DM_EMBED_CACHE", str(Path.home() / ".cache" / "dm_fastembed")),
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"),
        "HF_HUB_DISABLE_SYMLINKS": "1",
    }


def _reject_json_constant(value: str):
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _parse_dmjson(out: str, err: str):
    lines = [ln for ln in out.splitlines() if ln.startswith(_DMJSON_PREFIX)]
    if not lines:
        raise RuntimeError((err or out or "无输出").strip()[-300:])
    if len(lines) != 1:
        raise RuntimeError("子进程返回了多个 DMJSON 结果，协议不明确")
    line = lines[0]
    if len(line) > _MAX_PROTOCOL_LINE_CHARS:
        raise RuntimeError("子进程 DMJSON 结果超过大小上限")
    payload = line[len(_DMJSON_PREFIX):]
    try:
        return json.loads(payload, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"子进程 DMJSON 结果无效 ({exc.__class__.__name__})") from None


def run_isolated(module: str, argv: list, timeout: int):
    """同步跑 `python -m <module> <argv...>`，解析 DMJSON 结果；超时/无结果抛 RuntimeError。"""
    timeout = _timeout_seconds(timeout)
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


async def _stop_and_reap(proc) -> None:
    """Terminate an interrupted child and wait for the OS process record to be reaped."""
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    await proc.wait()


async def arun_isolated(module: str, argv: list, timeout: int):
    """异步版（FastMCP/asyncio 场景专用）。stdin 必须 DEVNULL——见模块 docstring。"""
    import asyncio
    timeout = _timeout_seconds(timeout)
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", module, *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=_sub_env())
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        await _stop_and_reap(proc)
        raise RuntimeError(f"子进程超时（{timeout}s）: {module}") from None
    except asyncio.CancelledError:
        await _stop_and_reap(proc)
        raise
    return _parse_dmjson(out_b.decode("utf-8", "replace"), err_b.decode("utf-8", "replace"))