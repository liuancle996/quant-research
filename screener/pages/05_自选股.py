"""
页面：自选股
============
展示自选股列表，支持添加/移除/导出 CSV。
"""

import sys
import csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from screener.favorites import add_favorite, remove_favorite, get_favorites
from screener.search import search_stocks
from screener.details import format_volume

st.set_page_config(
    page_title="自选股 — A股筛选器",
    page_icon="⭐",
    layout="wide",
)

st.title("⭐ 自选股")

# ── 添加自选股 ──
st.subheader("➕ 添加自选股")

col_search, col_btn = st.columns([4, 1])
with col_search:
    query = st.text_input(
        "🔍 搜索股票（输入代码或名称）",
        placeholder="例如: 000001, 平安银行",
        key="fav_search",
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    search_clicked = st.button("搜索", use_container_width=True, key="fav_search_btn")

add_code = None
add_name = None

if query and query.strip():
    results = search_stocks(query)
    if results:
        if len(results) == 1:
            add_code = results[0]["code"]
            add_name = results[0]["name"]
            st.caption(f"已匹配: {add_name}（{add_code}）")
        else:
            options = [f"{r['code']} — {r['name']} ({r['market']})" for r in results]
            selected_label = st.selectbox(
                "请选择要添加的股票",
                options,
                key="fav_select",
            )
            if selected_label:
                idx = options.index(selected_label)
                add_code = results[idx]["code"]
                add_name = results[idx]["name"]
    else:
        st.info(f"未找到匹配 \"{query}\" 的股票")

if add_code and add_name:
    if st.button(f"⭐ 加入自选: {add_name}（{add_code}）", use_container_width=True, key="fav_add_btn"):
        add_favorite(add_code, add_name)
        st.success(f"已添加 {add_name}（{add_code}）到自选股！")
        st.rerun()

# ── 自选列表 ──
st.markdown("---")
st.subheader("📋 我的自选股列表")

favorites = get_favorites()

if favorites:
    # 构建 DataFrame
    rows = []
    for f in favorites:
        pct_str = f"{f['pct_change']:+.2f}%" if f['pct_change'] is not None else "--"
        vol_str = format_volume(f['volume']) if f['volume'] is not None else "--"
        price_str = f"¥{f['latest_price']:.2f}" if f['latest_price'] is not None else "--"
        rows.append({
            "代码": f["code"],
            "名称": f["name"],
            "最新价": price_str,
            "涨跌幅": pct_str,
            "成交量": vol_str,
            "添加时间": f["added_at"],
        })

    df = pd.DataFrame(rows)

    # 显示表格
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "代码": st.column_config.TextColumn(width="small"),
            "名称": st.column_config.TextColumn(width="medium"),
            "最新价": st.column_config.TextColumn(width="small"),
            "涨跌幅": st.column_config.TextColumn(width="small"),
            "成交量": st.column_config.TextColumn(width="small"),
            "添加时间": st.column_config.TextColumn(width="medium"),
        },
    )

    # 移除按钮 + 导出
    col_rm, col_exp = st.columns([1, 1])
    with col_rm:
        remove_codes = [f["code"] for f in favorites]
        to_remove = st.selectbox(
            "选择要移除的股票",
            options=[f"{f['code']} — {f['name']}" for f in favorites],
            key="fav_remove_select",
        )
        if to_remove:
            remove_code = to_remove.split(" — ")[0]
            if st.button("❌ 移除选中股票", use_container_width=True, key="fav_remove_btn"):
                remove_favorite(remove_code)
                st.success(f"已移除 {remove_code}")
                st.rerun()

    with col_exp:
        st.markdown("<br>", unsafe_allow_html=True)
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 导出 CSV",
            data=csv_data,
            file_name="自选股.csv",
            mime="text/csv",
            use_container_width=True,
        )
else:
    st.info("⭐ 自选股列表为空，请在上方搜索添加股票。")

st.markdown("---")
st.caption("数据来源: hikyuu HDF5 | 本地 SQLite 存储")
