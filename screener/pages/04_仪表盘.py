"""
页面：仪表盘（默认首页）
========================
大盘概览（四大指数卡片）+ 涨跌家数统计 + 热门板块 Top 5。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from screener.stats import get_all_index_cards, get_index_card, get_up_down_stats
from screener.blocks import get_top_blocks

st.set_page_config(
    page_title="仪表盘 — A股筛选器",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 仪表盘")

# ── 第 1 行：四大指数卡片 ──────────────────────────────────
st.subheader("📈 大盘概览")

index_names = ["上证指数", "深证成指", "沪深300", "创业板指"]
col1, col2, col3, col4 = st.columns(4)

for col, name in zip([col1, col2, col3, col4], index_names):
    card = get_index_card(name)
    with col:
        if card:
            pct = card["pct_change"]
            delta_str = f"{pct:+.2f}%"
            if pct > 0:
                st.metric(
                    label=card["name"],
                    value=f"{card['latest']:,.2f}",
                    delta=delta_str,
                    delta_color="normal",
                )
            else:
                st.metric(
                    label=card["name"],
                    value=f"{card['latest']:,.2f}",
                    delta=delta_str,
                    delta_color="inverse",
                )
        else:
            st.metric(label=name, value="--", delta="暂无数据")

# ── 第 2 行：涨跌家数统计 ──────────────────────────────────
st.markdown("---")
st.subheader("📊 涨跌家数统计")

stats = get_up_down_stats(exclude_st=True)

if stats and stats["total"] > 0:
    col_chart, col_info = st.columns([3, 1])

    with col_chart:
        df_stats = pd.DataFrame({
            "类型": ["上涨", "下跌", "平盘"],
            "数量": [stats["up"], stats["down"], stats["flat"]],
            "占比": [
                f"{stats['up'] / stats['total'] * 100:.1f}%",
                f"{stats['down'] / stats['total'] * 100:.1f}%",
                f"{stats['flat'] / stats['total'] * 100:.1f}%",
            ],
        })

        import plotly.express as px
        fig = px.bar(
            df_stats,
            x="类型",
            y="数量",
            text="占比",
            color="类型",
            color_discrete_map={
                "上涨": "#EF5350",
                "下跌": "#26A69A",
                "平盘": "#BDBDBD",
            },
            height=350,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            yaxis_title="股票数量",
            xaxis_title="",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_info:
        total = stats["total"]
        up = stats["up"]
        down = stats["down"]
        flat = stats["flat"]
        up_ratio = up / total * 100 if total > 0 else 0

        st.metric("总统计（排除 ST）", f"{total:,} 只")
        st.metric("上涨家数", f"{up:,}", delta=f"{up_ratio:.1f}%")
        st.metric("下跌家数", f"{down:,}")
        st.metric("平盘家数", f"{flat:,}")
else:
    st.info("暂无涨跌统计数据。")

# ── 第 3 行：热门板块 Top 5 ────────────────────────────────
st.markdown("---")
st.subheader("🔥 热门板块 Top 5")

with st.spinner("正在计算板块涨跌幅..."):
    top_blocks = get_top_blocks(n=5, category="行业板块", exclude_st=True)

if top_blocks:
    top_blocks_data = []
    for i, blk in enumerate(top_blocks, 1):
        direction = "📈" if blk["avg_pct"] >= 0 else "📉"
        top_blocks_data.append({
            "排名": i,
            "板块": f"{direction} {blk['name']}",
            "平均涨幅": f"{blk['avg_pct']:+.2f}%",
            "上涨/下跌": f"{blk['up_count']}/{blk['down_count']}",
            "参与统计": f"{blk['stock_count']} 只",
        })

    df_blocks = pd.DataFrame(top_blocks_data)
    st.dataframe(
        df_blocks,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("暂无板块数据。")

st.markdown("---")
st.caption(
    "数据来源: hikyuu HDF5 | "
    "板块涨跌幅为板块内所有满足条件的股票的平均值 | "
    "数据截止: 最近交易日"
)
