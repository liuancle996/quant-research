"""
Streamlit 前端 — A股筛选器
===========================
端口: 8082
布局: 左侧筛选面板 + 右侧结果表格 + 统计分布图
"""

import sys
import time
import logging

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# 必须在任何其他导入之前配置 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from .engine import screen  # noqa: E402 — engine 依赖 adapter 完成 hikyuu 导入

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="A股筛选器",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 标题 ──
st.title("📊 A股筛选器")

# ── 侧边栏：筛选条件 ─────────────────────────────────────
with st.sidebar:
    st.header("筛选条件")

    # 交易所多选
    markets = st.multiselect(
        "交易所",
        options=["SH", "SZ", "BJ"],
        default=["SH", "SZ"],
        format_func=lambda x: {"SH": "上证", "SZ": "深证", "BJ": "北证"}.get(x, x),
    )

    # 时间区间
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
        index=2,  # 默认 20 日
    )
    lookback_days = lookback_options[lookback_label]

    # 涨跌幅范围
    st.subheader("涨跌幅 (%)")
    col1, col2 = st.columns(2)
    with col1:
        min_pct = st.number_input(
            "最小",
            value=None,
            step=1.0,
            format="%f",
            placeholder="不限",
        )
    with col2:
        max_pct = st.number_input(
            "最大",
            value=None,
            step=1.0,
            format="%f",
            placeholder="不限",
        )

    # 最小成交量
    min_volume = st.number_input(
        "最小日均成交量 (股)",
        value=None,
        step=10000,
        format="%d",
        placeholder="不限",
    )

    # ST 开关
    exclude_st = st.checkbox("排除 ST", value=True)

    # 排序设置
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

    # 返回条数
    top_n = st.slider("返回条数", min_value=10, max_value=500, value=50, step=10)

    # ── 筛选按钮 ──
    run_button = st.button("🔍 开始筛选", type="primary", use_container_width=True)

# ── 主区域 ────────────────────────────────────────────

# 初始化 session state
if "df_result" not in st.session_state:
    st.session_state.df_result = None
if "run_time" not in st.session_state:
    st.session_state.run_time = None
if "error" not in st.session_state:
    st.session_state.error = None

# 当点击筛选按钮时执行
if run_button:
    if not markets:
        st.error("请至少选择一个交易所。")
    else:
        progress_placeholder = st.empty()
        with progress_placeholder.container():
            st.info("⏳ 正在全市场筛选，这可能需要 1-3 分钟...")
            progress_bar = st.progress(0, text="初始化...")

        try:
            start_ts = time.time()

            # 执行筛选（纯函数，无副作用）
            df_result = screen(
                markets=markets,
                lookback_days=lookback_days,
                min_pct=min_pct if min_pct is not None and min_pct != 0 else None,
                max_pct=max_pct if max_pct is not None else None,
                min_volume=min_volume if min_volume is not None and min_volume != 0 else None,
                exclude_st=exclude_st,
                top_n=top_n,
                sort_by=sort_by,
                ascending=ascending,
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
            progress_placeholder.empty()

# ── 显示状态信息 ──
if st.session_state.run_time is not None:
    st.sidebar.caption(
        f"⏱ 耗时: {st.session_state.run_time:.1f}s"
    )
    if st.session_state.df_result is not None:
        st.sidebar.success(
            f"共筛选出 **{len(st.session_state.df_result)}** 只股票"
        )

if st.session_state.error:
    st.error(st.session_state.error)

# ── 显示结果表格 ──
if st.session_state.df_result is not None and len(st.session_state.df_result) > 0:
    df = st.session_state.df_result

    st.subheader(f"📋 筛选结果（共 {len(df)} 只）")

    # 准备显示用的 DataFrame（格式化）
    display_df = df.copy()
    display_df["pct_change"] = display_df["pct_change"].apply(
        lambda x: f"{x:+.2f}%"
    )
    display_df["avg_volume"] = display_df["avg_volume"].apply(
        lambda x: f"{x:,}"
    )
    display_df["latest_volume"] = display_df["latest_volume"].apply(
        lambda x: f"{x:,}"
    )

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

    # CSV 导出按钮
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 导出 CSV",
        data=csv,
        file_name=f"screener_results_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

    # ── 统计分布图 ──
    st.subheader("📈 统计分布")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig1, ax1 = plt.subplots(figsize=(6, 3.5))
        pct_vals = df["pct_change"]
        ax1.hist(pct_vals, bins=20, color="#2196F3", edgecolor="white", alpha=0.85)
        ax1.axvline(x=0, color="red", linestyle="--", linewidth=0.8, alpha=0.6)
        ax1.set_xlabel("涨跌幅 (%)")
        ax1.set_ylabel("股票数量")
        ax1.set_title("涨幅分布")
        ax1.grid(axis="y", alpha=0.3)
        st.pyplot(fig1)

    with col_chart2:
        fig2, ax2 = plt.subplots(figsize=(6, 3.5))
        vol_vals = df["avg_volume"] / 1_0000  # 转为万股
        ax2.hist(vol_vals, bins=20, color="#FF9800", edgecolor="white", alpha=0.85)
        ax2.set_xlabel("日均成交量 (万股)")
        ax2.set_ylabel("股票数量")
        ax2.set_title("成交量分布")
        ax2.grid(axis="y", alpha=0.3)
        st.pyplot(fig2)

elif st.session_state.df_result is not None:
    st.warning("没有符合条件的股票。请尝试放宽筛选条件。")

# ── 页脚说明 ──
st.markdown("---")
st.caption(
    "数据来源: hikyuu HDF5 | 数据截止: 最近交易日 | "
    "非实时行情，仅供参考"
)
