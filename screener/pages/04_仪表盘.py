"""
页面：仪表盘（默认首页）
========================
大盘概览（四大指数卡片）+ 涨跌家数统计 + 热门板块（可配置 Top N + 板块明细展开）。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from screener.hikyuu_adapter import sm, Query
from screener.stats import get_all_index_cards, get_index_card, get_up_down_stats
from screener.blocks import get_top_blocks, get_block_stock_details

st.set_page_config(
    page_title="仪表盘 — A股筛选器",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 仪表盘")

# ── 数据时间标识 ────────────────────────────────────────────
try:
    s = sm["sz000001"]
    k = s.get_kdata(Query(-1))
    if len(k) > 0:
        data_date = str(k[-1].datetime)[:10]
    else:
        data_date = "暂无数据"
except Exception:
    data_date = "暂无数据"

st.caption(f"📅 数据日期: {data_date}")

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

# ── 第 3 行：热门板块（可配置 Top N + 板块明细展开）────────
st.markdown("---")
st.subheader("🔥 热门板块")

# 板块数 slider：5-30，步长 5，默认 10
top_n = st.slider("显示板块数量", min_value=5, max_value=30, value=10, step=5)

with st.spinner("正在计算板块涨跌幅..."):
    top_blocks = get_top_blocks(n=top_n, category="行业板块", exclude_st=True)

if top_blocks:
    for i, blk in enumerate(top_blocks, 1):
        direction = "📈" if blk["avg_pct"] >= 0 else "📉"
        label = f"**#{i}** {direction} **{blk['name']}** &nbsp;&nbsp; "
        label += f"平均涨幅: {blk['avg_pct']:+.2f}% &nbsp;&nbsp; "
        label += f"上涨/下跌: {blk['up_count']}/{blk['down_count']} &nbsp;&nbsp; "
        label += f"统计: {blk['stock_count']} 只"

        with st.expander(label, expanded=False):
            details = get_block_stock_details("行业板块", blk["name"])
            if details:
                detail_rows = []
                for j, d in enumerate(details, 1):
                    detail_rows.append({
                        "排名": j,
                        "代码": d["code"],
                        "名称": d["name"],
                        "最新价": f"¥{d['latest_price']:.2f}",
                        "涨跌幅": f"{d['pct_change']:+.2f}%",
                        "成交量": f"{d['volume']:,}",
                    })
                df_detail = pd.DataFrame(detail_rows)
                st.dataframe(
                    df_detail,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("该板块内暂无符合条件的股票数据。")
else:
    st.info("暂无板块数据。")

st.markdown("---")
st.caption(
    "数据来源: hikyuu HDF5 | "
    "板块涨跌幅为板块内所有满足条件的股票的平均值 | "
    f"数据截止: {data_date}"
)
