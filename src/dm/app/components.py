"""可复用视觉件：返回 HTML 片段（配合 theme.py 的类名），或直接渲染。

约定：纯展示块（KPI 卡排 / 管道 / 时间线 / chip / 迷你条）走自定义 HTML（一次性 st.markdown），
含图表/表格的卡片用 card() 上下文（基于 st.container(border=True)）以稳妥承载 Streamlit 控件。
"""
from __future__ import annotations

import contextlib
import html as _html
import re

from . import theme as T

_STATE = {"ok": T.GREEN, "info": T.BLUE, "warn": T.AMBER, "bad": T.RED, "muted": T.HINT}


def html(s: str):
    import streamlit as st
    st.markdown(s, unsafe_allow_html=True)


def esc(s) -> str:
    return _html.escape(str(s))


def dot_color(state: str) -> str:
    return _STATE.get(state, T.HINT)


# ---------------- KPI 状态卡 ----------------
def kpi_card(label, value, unit="", state="info") -> str:
    u = f'<span class="u"> {esc(unit)}</span>' if unit else ""
    return (f'<div class="dm-kpi"><div class="dm-kpi-l">'
            f'<span class="dm-dot" style="background:{dot_color(state)}"></span>{esc(label)}</div>'
            f'<div class="dm-kpi-v">{esc(value)}{u}</div></div>')


def kpi_row(items, min_w=140):
    """items: list of (label, value, unit, state) 或 dict。一次性渲染一排 KPI。"""
    cards = []
    for it in items:
        if isinstance(it, dict):
            cards.append(kpi_card(it["label"], it["value"], it.get("unit", ""), it.get("state", "info")))
        else:
            label, value, *rest = it
            unit = rest[0] if len(rest) > 0 else ""
            state = rest[1] if len(rest) > 1 else "info"
            cards.append(kpi_card(label, value, unit, state))
    html(f'<div class="dm-grid" style="grid-template-columns:repeat(auto-fit,minmax({min_w}px,1fr))">'
         + "".join(cards) + "</div>")


# ---------------- chip / 状态灯 ----------------
def chip(text, kind="", icon="") -> str:
    pre = f"{icon} " if icon else ""
    return f'<span class="dm-chip {kind}">{pre}{esc(text)}</span>'


def status_light(text, state="ok") -> str:
    return (f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:{T.MUTED}">'
            f'<span class="dm-dot" style="background:{dot_color(state)}"></span>{esc(text)}</span>')


# ---------------- 实时同步管道 ----------------
def pipeline(nodes, foot=None):
    """nodes: list of dict(cls, icon, name, desc)；cls ∈ src/flow/sink/down。foot: list[str(html)]。"""
    arrow = '<span class="dm-arrow">→</span>'
    parts = []
    for i, n in enumerate(nodes):
        if i:
            parts.append(arrow)
        parts.append(
            f'<div class="dm-node {n["cls"]}"><div class="ic">{n["icon"]}</div>'
            f'<div class="nm">{esc(n["name"])}</div><div class="ds">{esc(n["desc"])}</div></div>')
    footh = ""
    if foot:
        footh = '<div class="dm-pipe-foot">' + "".join(f"<span>{x}</span>" for x in foot) + "</div>"
    html(f'<div class="dm-pipe">{"".join(parts)}</div>{footh}')


# ---------------- 任务链时间线 ----------------
_TL = {
    "question": ("❓", "#E6F1FB"), "plan": ("📝", "#E6F1FB"), "tool": ("🔧", "#E6F1FB"),
    "result": ("📥", "#E1F5EE"), "answer": ("✅", "#EAF3DE"),
}
_KW = (r"\b(SELECT|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|LEFT\s+JOIN|INNER\s+JOIN|JOIN|ON|AND|OR|"
       r"SUM|COUNT|AVG|MAX|MIN|LIMIT|AS|DESC|ASC|HAVING|DISTINCT|IN|IS|NULL|NOT)\b")


def sql_card(sql: str) -> str:
    e = esc(sql).strip()
    e = re.sub(_KW, lambda m: f'<span class="kw">{m.group(0)}</span>', e, flags=re.I)
    return f'<div class="dm-sql">{e}</div>'


def bubble(text: str) -> str:
    return f'<div class="dm-bubble">{esc(text)}</div>'


def answer_card(text: str) -> str:
    return f'<div class="dm-answer">{esc(text)}</div>'


def timeline(items):
    """items: list of dict(kind, label, body_html)。kind ∈ question/plan/tool/result/answer。"""
    rows = []
    for it in items:
        icon, bg = _TL.get(it["kind"], ("·", T.SURFACE))
        rows.append(
            f'<div class="dm-tl-i"><span class="dm-tl-dot" style="background:{bg}">{icon}</span>'
            f'<div class="dm-tl-k">{esc(it["label"])}</div>{it["body_html"]}</div>')
    html(f'<div class="dm-tl">{"".join(rows)}</div>')


# ---------------- 迷你横条 ----------------
def bar_list(rows, max_v=None, color=None):
    """rows: list of (label, value, display?)。按 value 画占比条。"""
    vals = [r[1] for r in rows] or [0]
    mx = max_v or max(vals) or 1
    color = color or T.BLUE
    out = []
    for r in rows:
        label, value = r[0], r[1]
        disp = r[2] if len(r) > 2 else value
        frac = max(2, round(value / mx * 100)) if mx else 0
        out.append(
            f'<div class="dm-bar-row"><div class="dm-bar-h"><span>{esc(label)}</span>'
            f'<span class="v">{esc(disp)}</span></div>'
            f'<div class="dm-bar-tr"><div class="dm-bar-fl" style="width:{frac}%;background:{color}"></div></div></div>')
    html("".join(out))


# ---------------- 卡片容器（承载图表/表格）----------------
def section_title(title, sub=None) -> str:
    subh = f'<span class="sub">{esc(sub)}</span>' if sub else ""
    return f'<div class="dm-card-t">{esc(title)}{subh}</div>'


@contextlib.contextmanager
def card(title=None, sub=None):
    import streamlit as st
    c = st.container(border=True)
    with c:
        if title:
            st.markdown(section_title(title, sub), unsafe_allow_html=True)
        yield c


def banner(text: str):
    html(f'<div class="dm-banner">⚠️ {esc(text)}</div>')
