"""Plotly 图表封装：全部走 theme.style_fig，保证浅色商务蓝一致观感。

返回 go.Figure；页面用 st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})。
"""
from __future__ import annotations

import plotly.graph_objects as go

from . import theme as T


def donut(labels, values, colors=None, center=None, height=190):
    """环形图。center 可在中心显示一个大字（如总数）。"""
    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=0.62, sort=False,
        marker=dict(colors=colors or T.CHART_COLORWAY, line=dict(color="#fff", width=2)),
        textinfo="none", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
    ))
    if center is not None:
        fig.add_annotation(text=str(center), x=0.5, y=0.5, showarrow=False,
                           font=dict(size=22, color=T.INK, family=T.FONT))
    return T.style_fig(fig, height=height, margin=dict(l=4, r=4, t=4, b=4))


def gauge(value, vmax=100, suffix="%", title=None, height=200):
    """半圆仪表盘（如 Eval 通过率）。value 0..vmax。"""
    color = T.GREEN if value >= 85 else (T.AMBER if value >= 60 else T.RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(suffix=suffix, font=dict(size=30, color=T.INK, family=T.FONT)),
        gauge=dict(
            axis=dict(range=[0, vmax], tickwidth=1, tickcolor=T.LINE, tickfont=dict(color=T.MUTED, size=10)),
            bar=dict(color=color, thickness=0.32),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[dict(range=[0, vmax], color=T.SURFACE)],
        ),
        title=dict(text=title or "", font=dict(size=13, color=T.MUTED, family=T.FONT)),
    ))
    return T.style_fig(fig, height=height, margin=dict(l=18, r=18, t=30, b=6))


def trend_line(x, y, name="", height=210, fill=True):
    """趋势折线（如问答量 / 通过率随时间）。"""
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers", name=name,
        line=dict(color=T.BLUE, width=2.4, shape="spline"),
        marker=dict(size=6, color=T.BLUE),
        fill="tozeroy" if fill else None, fillcolor="rgba(24,95,165,0.10)",
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    return T.style_fig(fig, height=height)


def bar(categories, values, colors=None, horizontal=True, height=None, fmt=None):
    """柱状/条形图（如按类别通过率 / 命中表 Top / 表行数）。"""
    n = len(list(categories))
    if horizontal:
        cats, vals = list(categories)[::-1], list(values)[::-1]
        fig = go.Figure(go.Bar(
            x=vals, y=cats, orientation="h",
            marker=dict(color=colors or T.BLUE),
            text=[(fmt or str)(v) for v in vals], textposition="auto",
            hovertemplate="%{y}: %{x}<extra></extra>",
        ))
        fig.update_xaxes(showgrid=True, gridcolor=T.LINE)
        fig.update_yaxes(showgrid=False)
        height = height or max(120, n * 34 + 40)
    else:
        fig = go.Figure(go.Bar(
            x=list(categories), y=list(values),
            marker=dict(color=colors or T.BLUE),
            text=[(fmt or str)(v) for v in values], textposition="outside",
            hovertemplate="%{x}: %{y}<extra></extra>",
        ))
        height = height or 230
    return T.style_fig(fig, height=height)


def latency_hist(values, height=210, nbins=24):
    """耗时分布直方图（MCP 调用 duration_ms）。"""
    fig = go.Figure(go.Histogram(
        x=list(values), nbinsx=nbins, marker=dict(color=T.BLUE_L, line=dict(color="#fff", width=0.5)),
        hovertemplate="%{x} ms: %{y} 次<extra></extra>",
    ))
    fig.update_xaxes(title_text="耗时 (ms)", title_font=dict(size=11, color=T.MUTED))
    return T.style_fig(fig, height=height)
