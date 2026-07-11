"""数据层：把留痕日志聚合成图表可用结构 + 实时探测平台健康/同步状态。

两类函数：
- 纯聚合（agg_audit / agg_sessions / agg_eval …）：只吃 list[dict]，无副作用、可单测。
- 实时探测（wh_* / flink_status / pg_slots / sr_pg_parity）：连 StarRocks / Flink REST / Postgres；
  全部 graceful——不可达只返回降级态、不抛异常；用 st.cache_data 短 TTL 去重，避免每次 rerun 重复打点。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

try:  # 缓存装饰器：Streamlit 在则短 TTL 缓存，不在则 no-op（便于单测纯聚合）
    import streamlit as st

    def _cache(ttl=8):
        return st.cache_data(ttl=ttl, show_spinner=False)
except ModuleNotFoundError:  # pragma: no cover
    def _cache(ttl=8):
        def deco(fn):
            return fn
        return deco


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except Exception:  # noqa: BLE001
        return None


# ============================ 纯聚合 ============================
def agg_audit(logs) -> dict:
    n = len(logs)
    ok = sum(1 for r in logs if r.get("ok"))
    durs = [r["duration_ms"] for r in logs if isinstance(r.get("duration_ms"), (int, float))]
    tools = Counter((r.get("tool_name") or "?") for r in logs)
    tables = Counter()
    for r in logs:
        for t in str(r.get("tables_touched") or "").split(","):
            t = t.strip()
            if t:
                tables[t] += 1
    return {
        "total": n, "ok": ok, "fail": n - ok,
        "success_rate": round(ok / n * 100) if n else None,
        "avg_ms": round(sum(durs) / len(durs)) if durs else None,
        "by_tool": dict(tools),
        "by_table": tables.most_common(8),
        "durations": durs,
        "failures": [r for r in logs if not r.get("ok")][-20:][::-1],
        "recent": logs[-15:][::-1],
    }


def agg_sessions(steps) -> dict:
    order = list(dict.fromkeys(s.get("session_id") for s in steps if s.get("session_id")))
    channels, step_counts, recent, days = Counter(), [], [], Counter()
    for sid in order:
        ss = sorted((s for s in steps if s.get("session_id") == sid), key=lambda s: s.get("step_no", 0))
        head = ss[0] if ss else {}
        channels[head.get("channel") or "?"] += 1
        step_counts.append(len(ss))
        final = next((s["final_answer"] for s in reversed(ss) if s.get("final_answer")), "")
        recent.append({"sid": sid, "question": head.get("question", ""), "answer": final,
                       "channel": head.get("channel", ""), "ts": head.get("ts", ""), "steps": len(ss)})
        ts = _ts(head.get("ts"))
        if ts:
            days[ts.date().isoformat()] += 1
    trend = sorted(days.items())
    return {
        "n_sessions": len(order), "n_questions": len(order),
        "avg_steps": round(sum(step_counts) / len(step_counts), 1) if step_counts else None,
        "by_channel": dict(channels),
        "recent": recent[::-1], "order": order,
        "trend_x": [d for d, _ in trend], "trend_y": [c for _, c in trend],
    }


def session_steps(sid, steps):
    return sorted((s for s in steps if s.get("session_id") == sid), key=lambda s: s.get("step_no", 0))


def parse_tool_call(content):
    """agent_session 里 tool_call 的 content = 'mcp__dm__run_sql  {json}' → (短名, args dict)。"""
    s = str(content)
    name, _, rest = s.partition("  ")
    short = name.split("__")[-1].strip()
    try:
        args = json.loads(rest)
    except Exception:  # noqa: BLE001
        args = {}
    return short, args


def agg_eval(runs) -> dict:
    order = list(dict.fromkeys(r.get("run_id") for r in runs if r.get("run_id")))
    by = {rid: [r for r in runs if r.get("run_id") == rid] for rid in order}
    trend = []
    for rid in order:
        rr = by[rid]
        total = len(rr)
        passed = sum(1 for r in rr if r.get("passed"))
        trend.append({"run_id": rid, "total": total, "passed": passed,
                      "rate": round(passed / total * 100) if total else 0,
                      "ts": rr[0].get("ts") if rr else ""})
    latest_rows = by[order[-1]] if order else []
    cats = {}
    for r in latest_rows:
        c = r.get("category") or "?"
        cats.setdefault(c, [0, 0])
        cats[c][1] += 1
        if r.get("passed"):
            cats[c][0] += 1
    by_cat = [{"cat": c, "passed": v[0], "total": v[1], "rate": round(v[0] / v[1] * 100) if v[1] else 0}
              for c, v in cats.items()]
    return {"trend": trend, "latest": trend[-1] if trend else None,
            "latest_rows": latest_rows, "by_cat": by_cat, "order": order, "by_run": by}


# ============================ 实时探测（graceful）============================
@_cache(ttl=6)
def wh_health() -> dict:
    import time as _t
    from dm.config import WH_DB, WH_HOST, WH_PORT
    from dm.warehouse.store import connect_ro
    info = {"host": WH_HOST, "port": WH_PORT, "db": WH_DB, "ok": False, "latency_ms": None, "error": ""}
    try:
        t0 = _t.perf_counter()
        con = connect_ro()
        con.execute("SELECT 1").fetchone()
        con.close()
        info["ok"] = True
        info["latency_ms"] = round((_t.perf_counter() - t0) * 1000)
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)
    return info


@_cache(ttl=10)
def wh_table_stats() -> dict:
    from dm.schema import TABLES
    from dm.warehouse.store import connect_ro
    out = {"rows": [], "total": 0, "n_tables": len(TABLES), "n_nonempty": 0,
           "freshness": None, "ok": False, "error": ""}
    try:
        con = connect_ro()
        try:
            for t in TABLES:
                try:
                    n = con.execute(f'SELECT COUNT(*) FROM `{t["name"]}`').fetchone()[0]
                except Exception:  # noqa: BLE001
                    n = None
                out["rows"].append({"table": t["name"], "cn": t["cn"], "rows": n})
                if n:
                    out["total"] += n
                    out["n_nonempty"] += 1
            try:
                f = con.execute("SELECT MAX(update_time) FROM inventory").fetchone()[0]
                out["freshness"] = str(f) if f else None
            except Exception:  # noqa: BLE001
                pass
            out["ok"] = True
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


@_cache(ttl=6)
def flink_status() -> dict:
    import requests
    from dm.config import FLINK_URL
    out = {"ok": False, "url": FLINK_URL, "version": None, "taskmanagers": None,
           "slots_total": None, "slots_available": None, "jobs_running": None,
           "jobs_failed": None, "jobs": [], "cdc": None, "error": ""}
    try:
        ov = requests.get(f"{FLINK_URL}/overview", timeout=5).json()
        out.update(version=ov.get("flink-version"), taskmanagers=ov.get("taskmanagers"),
                   slots_total=ov.get("slots-total"), slots_available=ov.get("slots-available"),
                   jobs_running=ov.get("jobs-running"), jobs_failed=ov.get("jobs-failed"))
        jo = requests.get(f"{FLINK_URL}/jobs/overview", timeout=5).json()
        for j in jo.get("jobs", []):
            tk = j.get("tasks", {})
            out["jobs"].append({
                "jid": j.get("jid"), "name": j.get("name"), "state": j.get("state"),
                "duration_ms": j.get("duration"), "start": j.get("start-time"),
                "t_running": tk.get("running"), "t_total": tk.get("total"), "t_failed": tk.get("failed")})
        running = [j for j in out["jobs"] if j["state"] == "RUNNING"]
        out["cdc"] = running[0] if running else (out["jobs"][0] if out["jobs"] else None)
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


@_cache(ttl=8)
def pg_slots() -> dict:
    out = {"ok": False, "available": True, "slots": [], "n_active": 0, "max_lag": None, "error": ""}
    try:
        import psycopg
    except ModuleNotFoundError:
        out["available"] = False
        out["error"] = "psycopg 未安装（pip install -e .[dev] 后可用）"
        return out
    from dm.config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
    try:
        with psycopg.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
                             dbname=PG_DB, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT slot_name, active, "
                    "pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag "
                    "FROM pg_replication_slots ORDER BY slot_name;")
                for name, active, lag in cur.fetchall():
                    out["slots"].append({"name": name, "active": bool(active),
                                         "lag": int(lag) if lag is not None else None})
        out["n_active"] = sum(1 for s in out["slots"] if s["active"])
        lags = [s["lag"] for s in out["slots"] if s["lag"] is not None]
        out["max_lag"] = max(lags) if lags else None
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


@_cache(ttl=15)
def sr_pg_parity() -> dict:
    from dm.schema import TABLES
    out = {"ok": False, "rows": [], "n_match": 0, "pg_ok": False, "error": ""}
    sr = {}
    try:
        from dm.warehouse.store import connect_ro
        con = connect_ro()
        try:
            for t in TABLES:
                try:
                    sr[t["name"]] = con.execute(f'SELECT COUNT(*) FROM `{t["name"]}`').fetchone()[0]
                except Exception:  # noqa: BLE001
                    sr[t["name"]] = None
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        out["error"] = f"StarRocks: {e}"
    pg = {}
    try:
        import psycopg
        from dm.config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
        with psycopg.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
                             dbname=PG_DB, connect_timeout=3) as conn:
            for t in TABLES:
                try:
                    with conn.cursor() as cur:
                        cur.execute(f'SELECT COUNT(*) FROM public."{t["name"]}"')
                        pg[t["name"]] = cur.fetchone()[0]
                except Exception:  # noqa: BLE001
                    conn.rollback()
                    pg[t["name"]] = None
        out["pg_ok"] = True
    except ModuleNotFoundError:
        out["error"] = (out["error"] + " psycopg 未安装").strip()
    except Exception as e:  # noqa: BLE001
        out["error"] = (out["error"] + f" PG: {e}").strip()
    for t in TABLES:
        s, p = sr.get(t["name"]), pg.get(t["name"])
        match = s is not None and p is not None and s == p
        out["rows"].append({"table": t["name"], "cn": t["cn"], "pg": p, "sr": s, "match": match})
        if match:
            out["n_match"] += 1
    out["ok"] = bool(sr)
    return out


def fmt_bytes(n):
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def fmt_duration(ms):
    if not ms:
        return "—"
    s = ms / 1000
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s / 60:.0f}m"
    return f"{s / 3600:.1f}h"
