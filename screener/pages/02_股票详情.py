"""
页面：股票详情
============
搜索股票 + 查看日 K 线图 + 均线叠加 + 技术指标副图 + 自选股收藏。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from screener.search import search_stocks
from screener.details import get_stock_info, get_kline_data, plot_kline, format_volume
from screener.favorites import add_favorite, remove_favorite, is_favorite

st.set_page_config(
    page_title="股票详情 — A股筛选器",
    page_icon="📈",
    layout="wide",
)

st.title("📈 股票详情")

# ── 搜索框 ──
search_query = st.text_input(
    "🔍 搜索股票（输入代码或名称）",
    placeholder="例如: 000001, 平安银行, 贵州茅台",
    key="detail_search",
)

# 搜索结果
selected_code = None
search_results = []

if search_query and search_query.strip():
    results = search_stocks(search_query)
    if results:
        # 如果只有一个精确匹配，直接选中
        if len(results) == 1:
            selected_code = results[0]["code"]
        else:
            search_results = results
            options = [f"{r['code']} — {r['name']} ({r['market']})  ¥{r['latest_price']:.2f}" for r in results]
            selected_label = st.selectbox("请选择股票", options, key="detail_select")
            if selected_label:
                idx = options.index(selected_label)
                selected_code = results[idx]["code"]
    else:
        st.info(f"未找到匹配 \"{search_query}\" 的股票")

# ── 详情展示 ──
if selected_code:
    info = get_stock_info(selected_code)
    if info and info.get("valid"):
        # 基本信息卡片 — 含收藏按钮
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            fav = is_favorite(selected_code)
            star_label = f"{'⭐' if fav else '☆'} 收藏" if not fav else "⭐ 已收藏"
            col_name, col_star = st.columns([3, 1])
            with col_name:
                st.metric(
                    label=f"{info['name']}（{info['code']}）",
                    value=f"¥{info['latest_price']:.2f}",
                    delta=f"{info['pct_change']:+.2f}%",
                )
            with col_star:
                if fav:
                    if st.button("★ 取消收藏", key=f"fav_remove_{selected_code}", use_container_width=True):
                        remove_favorite(selected_code)
                        st.rerun()
                else:
                    if st.button("☆ 加入收藏", key=f"fav_add_{selected_code}", use_container_width=True):
                        add_favorite(selected_code, info["name"])
                        st.rerun()
        with col2:
            market_label = {"SH": "上证", "SZ": "深证", "BJ": "北证"}.get(info["market"], info["market"])
            st.metric("交易所", market_label)
        with col3:
            st.metric("最新价", f"¥{info['latest_price']:.2f}")
        with col4:
            st.metric("成交量", format_volume(info["volume"]))

        # ── K 线设置 ──
        col_ma, col_ind, col_range = st.columns([1, 1, 1])
        with col_ma:
            ma_options = st.multiselect(
                "均线叠加",
                options=[5, 10, 20, 60],
                default=[5, 10, 20],
                format_func=lambda x: f"MA{x}",
            )
        with col_ind:
            indicator_options = st.multiselect(
                "指标叠加",
                options=["MACD", "RSI", "KDJ"],
                default=[],
            )
        with col_range:
            range_options = {
                "近 60 日": 60,
                "近 120 日": 120,
                "近 250 日": 250,
                "近 500 日": 500,
            }
            range_label = st.selectbox(
                "数据范围",
                options=list(range_options.keys()),
                index=1,
            )
            lookback = range_options[range_label]

        # ── K 线图 ──
        df = get_kline_data(selected_code, lookback=lookback)
        if df is not None and len(df) > 0:
            title = f"{info['name']}（{info['code']}）— 日K线图"
            fig = plot_kline(
                df,
                mas=ma_options if ma_options else None,
                indicators=indicator_options if indicator_options else None,
                title=title,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("未获取到 K 线数据。")
    else:
        st.error(f"未找到股票 {selected_code}，或该股票已退市/停牌。")
elif not search_query:
    st.info("请在搜索框输入股票代码或名称开始查询。")
