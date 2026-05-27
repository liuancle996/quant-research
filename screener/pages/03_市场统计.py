"""
页面：市场统计
============
大盘指数行情 + 涨幅榜/跌幅榜/成交量榜 + 涨跌分布。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from screener.stats import (
    get_all_index_cards,
    get_top_gainers,
    get_top_losers,
    get_top_volume,
    get_up_down_stats,
)
from screener.hikyuu_adapter import sm, Query

st.set_page_config(
    page_title="市场统计 — A股筛选器",
    page_icon="📊",
    layout="wide",
)

st.title("📊 市场统计")

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

# ── 大盘指数行情 ──────────────────────────────────────────
st.subheader("🏛️ 大盘指数")

index_cards = get_all_index_cards()
if index_cards:
    cols = st.columns(len(index_cards))
    for i, card in enumerate(index_cards):
        with cols[i]:
            st.metric(
                label=card["name"],
                value=f"{card['latest']:.2f}",
                delta=f"{card['pct_change']:+.2f}%",
            )
else:
    st.warning("暂未获取到指数数据。")

# ── 涨跌统计 ──────────────────────────────────────────────
st.subheader("📈 涨跌分布")

up_down = get_up_down_stats()
if up_down["total"] > 0:
    col_u, col_d, col_f, col_t = st.columns(4)
    with col_u:
        st.metric("上涨", up_down["up"], delta_color="off")
    with col_d:
        st.metric("下跌", up_down["down"], delta_color="off")
    with col_f:
        st.metric("平盘", up_down["flat"], delta_color="off")
    with col_t:
        total_label = up_down["total"]
        up_pct = round(up_down["up"] / up_down["total"] * 100, 1) if up_down["total"] > 0 else 0
        st.metric("总计", total_label, f"上涨占比 {up_pct}%")

    # 柱状图
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 3))
    categories = ["上涨", "下跌", "平盘"]
    values = [up_down["up"], up_down["down"], up_down["flat"]]
    colors = ["#FF4444", "#4CAF50", "#999999"]
    bars = ax.bar(categories, values, color=colors, edgecolor="white", alpha=0.85)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                str(v), ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_ylabel("股票数量")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("今日涨跌家数")
    st.pyplot(fig, use_container_width=False)
else:
    st.info("暂未获取到涨跌统计数据。")

# ── 三大排行榜 ─────────────────────────────────────────────
st.subheader("🏆 排行榜")

tab1, tab2, tab3 = st.tabs(["🚀 涨幅榜 Top 10", "📉 跌幅榜 Top 10", "📊 成交量榜 Top 10"])


def _render_rank_table(title: str, items: list[dict], value_label: str, value_fmt: str):
    """渲染排名表格。"""
    if not items:
        st.info(f"暂未获取到{title}数据。")
        return
    rows = []
    for i, item in enumerate(items, 1):
        if value_fmt == "pct":
            value_str = f"{item['value']:+.2f}%"
        elif value_fmt == "vol":
            if item["value"] >= 1_0000_0000:
                value_str = f"{item['value'] / 1_0000_0000:.2f}亿"
            elif item["value"] >= 1_0000:
                value_str = f"{item['value'] / 1_0000:.2f}万"
            else:
                value_str = str(item["value"])
        else:
            value_str = str(item["value"])
        rows.append({
            "排名": i,
            "代码": item["code"],
            "名称": item["name"],
            "交易所": {"SH": "上证", "SZ": "深证", "BJ": "北证"}.get(item["market"], item["market"]),
            "最新价": f"¥{item['latest_price']:.2f}",
            value_label: value_str,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


with tab1:
    _render_rank_table("涨幅榜", get_top_gainers(), "涨跌幅", "pct")

with tab2:
    _render_rank_table("跌幅榜", get_top_losers(), "涨跌幅", "pct")

with tab3:
    _render_rank_table("成交量榜", get_top_volume(), "成交量", "vol")

st.markdown("---")
st.caption("数据来源: hikyuu HDF5 | 数据截止: 最近交易日 | 非实时行情，仅供参考")
