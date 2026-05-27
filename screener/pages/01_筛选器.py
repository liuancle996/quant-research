"""
页面：筛选器
============
把原有 app.py 的筛选器逻辑搬至独立页面。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from screener.engine import screen


st.set_page_config(
    page_title="筛选器 — A股筛选器",
    page_icon="📊",
    layout="wide",
)

st.title("📊 筛选器")

# ── 筛选条件（主内容区 expander）─────────────────────────
with st.expander("🔍 筛选条件", expanded=True):
    markets = st.multiselect(
        "交易所",
        options=["SH", "SZ", "BJ"],
        default=["SH", "SZ"],
        format_func=lambda x: {"SH": "上证", "SZ": "深证", "BJ": "北证"}.get(x, x),
    )

    lookback_options = {
        "5 日": 5,
        "10 日": 10,
        "20 日(1月)": 20,
        "60 日(3月)": 60,
        "120 日(半年)": 120,
        "250 日(1年)": 250,
    }
    lookback_label = st.selectbox(
        "时间区间",
        options=list(lookback_options.keys()),
        index=2,
    )
    lookback_days = lookback_options[lookback_label]

    st.subheader("涨跌幅 (%)")
    col1, col2 = st.columns(2)
    with col1:
        min_pct = st.number_input(
            "最小", value=None, step=1.0, format="%f", placeholder="不限",
        )
    with col2:
        max_pct = st.number_input(
            "最大", value=None, step=1.0, format="%f", placeholder="不限",
        )

    min_volume = st.number_input(
        "最小日均成交量 (股)",
        value=None, step=10000, format="%d", placeholder="不限",
    )

    exclude_st = st.checkbox("排除 ST", value=True)

    st.divider()
    st.subheader("板块筛选")
    block_disabled = False
    block_category_options = ["不限", "行业板块", "概念板块"]
    block_category_label = st.selectbox(
        "板块分类",
        options=block_category_options,
        index=0,
        key="blk_cat",
    )
    block_name = None
    block_category = None
    if block_category_label == "不限":
        block_name_options = ["不限"]
        block_disabled = True
    else:
        from screener.blocks import get_block_list

        block_category = block_category_label
        blk_list = get_block_list(block_category)
        block_name_options = ["不限"] + [b["name"] for b in blk_list]

    block_name_label = st.selectbox(
        "板块名称",
        options=block_name_options,
        index=0,
        key="blk_name",
        disabled=block_disabled,
    )
    if block_name_label and block_name_label != "不限":
        block_name = block_name_label

    st.subheader("排序")
    col3, col4 = st.columns(2)
    with col3:
        sort_by = st.selectbox(
            "排序字段",
            options=["pct_change", "avg_volume", "latest_volume", "latest_price"],
            format_func=lambda x: {
                "pct_change": "涨跌幅",
                "avg_volume": "日均成交量",
                "latest_volume": "最新成交量",
                "latest_price": "最新价",
            }.get(x, x),
        )
    with col4:
        ascending = st.checkbox("升序", value=False)

    top_n = st.slider("返回条数", min_value=10, max_value=500, value=50, step=10)

    run_button = st.button("🔍 开始筛选", type="primary", use_container_width=True)

# ── 主区域 ────────────────────────────────────────────────

if "df_result" not in st.session_state:
    st.session_state.df_result = None
if "run_time" not in st.session_state:
    st.session_state.run_time = None
if "error" not in st.session_state:
    st.session_state.error = None

if run_button:
    if not markets:
        st.error("请至少选择一个交易所。")
    else:
        status = st.empty()
        block_info = ""
        if block_category and block_name:
            block_info = f"（板块: {block_category} - {block_name}）"
        status.info(f"⏳ 正在筛选{block_info}，请稍候...")

        try:
            start_ts = time.time()
            df_result = screen(
                markets=markets,
                lookback_days=lookback_days,
                min_pct=min_pct if min_pct is not None else None,
                max_pct=max_pct if max_pct is not None else None,
                min_volume=min_volume if min_volume is not None and min_volume > 0 else None,
                exclude_st=exclude_st,
                top_n=top_n,
                sort_by=sort_by,
                ascending=ascending,
                block_category=block_category,
                block_name=block_name,
            )
            elapsed = time.time() - start_ts
            st.session_state.df_result = df_result
            st.session_state.run_time = elapsed
            st.session_state.error = None

        except RuntimeError as e:
            st.session_state.error = str(e)
            st.session_state.df_result = None
        except Exception as e:
            st.session_state.error = f"筛选过程中发生错误: {e}"
            st.session_state.df_result = None
        finally:
            status.empty()

# ── 状态信息 ──
if st.session_state.run_time is not None:
    st.sidebar.caption(f"⏱ 耗时: {st.session_state.run_time:.1f}s")
    if st.session_state.df_result is not None:
        st.sidebar.success(
            f"共筛选出 **{len(st.session_state.df_result)}** 只股票"
        )

if st.session_state.error:
    st.error(st.session_state.error)

# ── 结果表格 ──
if st.session_state.df_result is not None and len(st.session_state.df_result) > 0:
    df = st.session_state.df_result

    st.subheader(f"📋 筛选结果（共 {len(df)} 只）")

    display_df = df.copy()
    display_df["pct_change"] = display_df["pct_change"].apply(lambda x: f"{x:+.2f}%")
    display_df["avg_volume"] = display_df["avg_volume"].apply(lambda x: f"{x:,}")
    display_df["latest_volume"] = display_df["latest_volume"].apply(lambda x: f"{x:,}")

    column_config = {
        "code": "代码",
        "name": "名称",
        "market": "交易所",
        "latest_price": st.column_config.NumberColumn("最新价", format="¥%.2f"),
        "start_price": st.column_config.NumberColumn("起始价", format="¥%.2f"),
        "end_price": st.column_config.NumberColumn("结束价", format="¥%.2f"),
        "pct_change": "涨跌幅",
        "avg_volume": "日均成交量",
        "latest_volume": "最新成交量",
        "n_days": "交易日数",
    }

    st.dataframe(
        display_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=min(600, len(df) * 35 + 40),
    )

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 导出 CSV",
        data=csv,
        file_name=f"screener_results_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

    st.subheader("📈 统计分布")
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig1, ax1 = plt.subplots(figsize=(6, 3.5))
        ax1.hist(df["pct_change"], bins=20, color="#2196F3", edgecolor="white", alpha=0.85)
        ax1.axvline(x=0, color="red", linestyle="--", linewidth=0.8, alpha=0.6)
        ax1.set_xlabel("涨跌幅 (%)")
        ax1.set_ylabel("股票数量")
        ax1.set_title("涨幅分布")
        ax1.grid(axis="y", alpha=0.3)
        st.pyplot(fig1)

    with col_chart2:
        fig2, ax2 = plt.subplots(figsize=(6, 3.5))
        ax2.hist(df["avg_volume"] / 1_0000, bins=20, color="#FF9800", edgecolor="white", alpha=0.85)
        ax2.set_xlabel("日均成交量 (万股)")
        ax2.set_ylabel("股票数量")
        ax2.set_title("成交量分布")
        ax2.grid(axis="y", alpha=0.3)
        st.pyplot(fig2)

elif st.session_state.df_result is not None:
    st.warning("没有符合条件的股票。请尝试放宽筛选条件。")

st.markdown("---")
st.caption(
    "数据来源: hikyuu HDF5 | "
    "数据截止: 最近交易日 | "
    "非实时行情，仅供参考"
)

# 显示数据时间范围
try:
    from screener.hikyuu_adapter import sm as _sm, Query as _Query
    ref = _sm["sz000001"]
    k = ref.get_kdata(_Query(-1))
    if len(k) > 0:
        st.sidebar.divider()
        st.sidebar.caption(f"📅 数据日期: {str(k[0].datetime)[:10]}")
except Exception:
    pass
