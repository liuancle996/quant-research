"""
A股筛选器 — 多页面应用入口
============================
使用 st.navigation() + st.Page() 实现多页面路由。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

# ── 页面配置 ──
st.set_page_config(
    page_title="A股筛选器",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 定义页面 ──
pages = {
    "筛选分析": [
        st.Page("pages/01_筛选器.py", title="筛选器", icon="🔍"),
        st.Page("pages/02_股票详情.py", title="股票详情", icon="📈"),
        st.Page("pages/03_市场统计.py", title="市场统计", icon="📊"),
    ],
}

# ── 导航 ──
pg = st.navigation(pages, position="sidebar")
pg.run()
