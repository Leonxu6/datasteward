"""浅色商务蓝设计系统：配色常量 + 注入式 CSS + 统一 Plotly 样式。

管理平台所有视觉件（KPI 卡 / 管道图 / 时间线 / chip）走自定义 HTML + 这里的类名；
图表走 charts.py（统一调用 style_fig）。颜色取自参考截图的商务蓝 + 语义色。
"""
from __future__ import annotations

# ---- 调色板（与样稿一致；商务蓝主色 + 语义色）----
INK = "#1A2B42"        # 主文本
MUTED = "#5F6B7C"      # 次文本
HINT = "#8A97A8"       # 提示文本
LINE = "#E3E9F2"       # 描边/分隔
CARD = "#FFFFFF"       # 卡片底
PAGE = "#F1F5FB"       # 页面底
SURFACE = "#F7FAFE"    # 浅表面

BLUE = "#185FA5"
BLUE_L = "#378ADD"
BLUE_LL = "#85B7EB"
NAVY = "#0C447C"       # 侧栏深蓝
GREEN = "#1D9E75"
GREEN_D = "#0F6E56"
AMBER = "#BA7517"
AMBER_L = "#EF9F27"
RED = "#E24B4A"
RED_D = "#A32D2D"
PURPLE = "#534AB7"

CHART_COLORWAY = [BLUE, GREEN, AMBER, BLUE_L, PURPLE, RED, BLUE_LL]
FONT = ('-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", '
        '"PingFang SC", "Source Sans Pro", sans-serif')


def style_fig(fig, height=None, legend=False, margin=None):
    """统一 Plotly 外观：透明底、紧边距、商务蓝 colorway、淡网格。"""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT, size=12, color=INK),
        margin=margin or dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        colorway=CHART_COLORWAY,
        height=height,
        hoverlabel=dict(font_size=12, font_family=FONT),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=LINE, zeroline=False, tickfont=dict(color=MUTED))
    return fig


_CSS = f"""
<style>
/* —— 整体留白与底色 —— */
.stApp {{ background:{PAGE}; }}
.block-container {{ padding-top:1.4rem; padding-bottom:2.5rem; max-width:1280px; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility:hidden; height:0; }}

/* —— 侧栏：商务深蓝 —— */
section[data-testid="stSidebar"] {{ background:{NAVY}; width:236px !important; }}
section[data-testid="stSidebar"] * {{ color:#DCE9F8; }}
section[data-testid="stSidebar"] .stRadio > label {{ display:none; }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:2px; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
  display:flex; align-items:center; width:100%; padding:9px 12px; margin:0;
  border-radius:9px; font-size:14px; cursor:pointer; transition:background .12s; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background:rgba(255,255,255,.08); }}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
  background:{BLUE}; color:#fff; font-weight:500; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display:none; }}
.dm-brand {{ display:flex; align-items:center; gap:8px; padding:4px 6px 14px; color:#EAF2FE; font-size:15px; font-weight:500; }}
.dm-side-foot {{ margin-top:10px; padding:10px 8px; border-top:1px solid rgba(255,255,255,.14);
  font-size:12px; line-height:1.7; color:#AEC4E4; }}

/* —— 顶部子标签（st.tabs）—— */
.stTabs [data-baseweb="tab-list"] {{ gap:20px; border-bottom:1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ padding:8px 2px; font-size:14px; color:{MUTED}; }}
.stTabs [aria-selected="true"] {{ color:{BLUE} !important; font-weight:500; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:{BLUE}; }}

/* —— 卡片 / 网格 —— */
.dm-grid {{ display:grid; gap:12px; margin-bottom:6px; }}
.dm-card {{ background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:16px 18px; }}
.dm-card-t {{ font-size:14px; font-weight:500; color:{INK}; margin-bottom:12px;
  display:flex; align-items:center; justify-content:space-between; }}
.dm-card-t .sub {{ font-size:12px; font-weight:400; color:{MUTED}; }}

/* —— KPI 状态卡 —— */
.dm-kpi {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:12px 14px; }}
.dm-kpi-l {{ font-size:12.5px; color:{MUTED}; display:flex; align-items:center; gap:6px; }}
.dm-kpi-v {{ font-size:23px; font-weight:500; color:{INK}; margin-top:4px; line-height:1.2; }}
.dm-kpi-v .u {{ font-size:12px; color:{HINT}; font-weight:400; }}
.dm-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; }}

/* —— chip —— */
.dm-chip {{ display:inline-flex; align-items:center; gap:5px; font-size:12px; padding:3px 9px;
  border-radius:8px; background:{SURFACE}; color:{MUTED}; }}
.dm-chip.ok {{ background:#E1F5EE; color:{GREEN_D}; }}
.dm-chip.info {{ background:#E6F1FB; color:{NAVY}; }}
.dm-chip.warn {{ background:#FAEEDA; color:{AMBER}; }}
.dm-chip.bad {{ background:#FCEBEB; color:{RED_D}; }}

/* —— 实时同步管道 —— */
.dm-pipe {{ display:flex; align-items:center; gap:8px; }}
.dm-node {{ flex:1; text-align:center; padding:14px 8px; border-radius:12px; }}
.dm-node .ic {{ font-size:24px; }}
.dm-node .nm {{ font-size:13px; font-weight:500; margin-top:5px; }}
.dm-node .ds {{ font-size:11.5px; margin-top:2px; }}
.dm-node.src, .dm-node.sink {{ background:#E1F5EE; }}
.dm-node.src .nm, .dm-node.sink .nm {{ color:{GREEN_D}; }}
.dm-node.src .ds, .dm-node.sink .ds {{ color:{GREEN}; }}
.dm-node.flow {{ background:#E6F1FB; }}
.dm-node.flow .nm {{ color:{NAVY}; }}
.dm-node.flow .ds {{ color:{BLUE}; }}
.dm-node.down {{ background:#FCEBEB; }}
.dm-node.down .nm {{ color:{RED_D}; }}
.dm-node.down .ds {{ color:{RED}; }}
.dm-arrow {{ color:{BLUE_L}; font-size:20px; }}
.dm-pipe-foot {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:14px; padding-top:11px;
  border-top:1px solid {LINE}; font-size:12px; color:{MUTED}; }}

/* —— 任务链时间线 —— */
.dm-tl {{ position:relative; padding-left:28px; }}
.dm-tl::before {{ content:""; position:absolute; left:10px; top:6px; bottom:6px; width:2px; background:{LINE}; }}
.dm-tl-i {{ position:relative; margin-bottom:14px; }}
.dm-tl-i:last-child {{ margin-bottom:0; }}
.dm-tl-dot {{ position:absolute; left:-28px; width:22px; height:22px; border-radius:50%;
  display:flex; align-items:center; justify-content:center; font-size:12px; }}
.dm-tl-k {{ font-size:11px; color:{MUTED}; margin-bottom:4px; }}
.dm-bubble {{ background:{SURFACE}; border:1px solid {LINE}; border-radius:10px; padding:9px 11px; font-size:13px; color:{INK}; }}
.dm-sql {{ background:{NAVY}; border-radius:10px; padding:9px 11px; font-size:12px;
  font-family:ui-monospace,Menlo,Consolas,monospace; color:#B5D4F4; white-space:pre-wrap; word-break:break-word; }}
.dm-sql .kw {{ color:#85B7EB; }} .dm-sql .st {{ color:#9FE1CB; }}
.dm-answer {{ background:#EAF3DE; border-radius:10px; padding:9px 11px; font-size:13px; color:#27500A; }}

/* —— 迷你横条（占比/滞后）—— */
.dm-bar-row {{ margin-bottom:9px; font-size:12.5px; }}
.dm-bar-h {{ display:flex; justify-content:space-between; margin-bottom:3px; color:{INK}; }}
.dm-bar-h .v {{ color:{MUTED}; }}
.dm-bar-tr {{ height:7px; background:{PAGE}; border-radius:5px; overflow:hidden; }}
.dm-bar-fl {{ height:7px; border-radius:5px; background:{BLUE}; }}

/* —— 杂项 —— */
.dm-h {{ font-size:18px; font-weight:500; color:{INK}; }}
.dm-muted {{ color:{MUTED}; font-size:13px; }}
.dm-banner {{ background:#FAEEDA; border:1px solid #F3D9A8; color:{AMBER}; border-radius:10px;
  padding:10px 14px; font-size:13px; }}
div[data-testid="stDataFrame"] {{ border:1px solid {LINE}; border-radius:10px; }}
</style>
"""


def inject_css():
    import streamlit as st
    st.markdown(_CSS, unsafe_allow_html=True)
