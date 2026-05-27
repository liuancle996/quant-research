"""因子实验室 — Streamlit 页面

选因子 + 调参数 → 跑分析 → IC/分层/衰减可视化
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from factor_lab.mf_builder import build_mf, get_a_share_universe
from factor_lab.extraction import extract_scores, get_or_compute_forward_returns
from factor_lab.evaluation import ic_analysis, quantile_returns, ic_decay
from factor_lab.factors import momentum, volatility, price_position, volume_ratio
from factor_lab.hikyuu_adapter import sm

st.set_page_config(
    page_title="因子实验室 — A股筛选器",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 因子实验室")

FACTOR_MAP = {
    "动量 (ROC)": (momentum, "动量因子：过去 N 日收益率"),
    "波动率": (volatility, "波动率因子：过去 N 日收益率标准差"),
    "价格位置": (price_position, "价格位置：当前价在过去 N 日高低区间的相对位置"),
    "量比": (volume_ratio, "量比因子：短期均量 / 长期均量"),
}

STOCK_POOL = {
    "沪深300": "hs300",
    "全量A股": "all",
}


def _trim_trailing_nan(df, threshold=0.95):
    while len(df) > 0 and df.iloc[-1].isna().mean() > threshold:
        df = df.iloc[:-1]
    return df


def run_analysis(factor_name, n, forward_days, stock_pool, normalize,
                 industry_neutral, market_cap_neutral, show_decay):
    """运行因子分析，返回结果 dict"""

    # 1. 股票池
    if stock_pool == "hs300":
        hs300_block = sm.get_block("指数板块", "沪深300")
        stocks = list(hs300_block)
    else:
        stocks = get_a_share_universe()

    # 2. 因子
    factor_fn = FACTOR_MAP[factor_name][0]
    indicator = factor_fn(n)

    # 3. 构建 MF
    mf, dates = build_mf(
        [indicator],
        stocks=stocks,
        start_date='20250101',
        end_date='20250620',
        normalize='zscore' if normalize else None,
        industry_neutral=industry_neutral,
        market_cap_neutral=market_cap_neutral,
    )

    # 4. 提取评分
    scores = extract_scores(mf, dates)

    # 5. 前向收益
    stock_codes = [s.market_code for s in stocks]
    fwd_returns = get_or_compute_forward_returns(
        mf, dates, forward_days=forward_days,
        stock_codes=stock_codes, start_date='20250101', end_date='20250620',
    )
    if fwd_returns.empty:
        return {'error': '无法计算前向收益，可能数据不足'}

    # 裁剪 + 对齐
    scores = _trim_trailing_nan(scores)
    fwd_returns = _trim_trailing_nan(fwd_returns)
    common = scores.index.intersection(fwd_returns.index)
    scores = scores.loc[common]
    fwd_returns = fwd_returns.loc[common]

    if len(scores) == 0:
        return {'error': '评分数据为空'}

    # 6. 评估
    ic = ic_analysis(scores, fwd_returns)
    qr = quantile_returns(scores, fwd_returns)

    # 7. IC 衰减（可选）
    decay = None
    if show_decay:
        decay_periods = [1, 5, 10, 20, 30, 60]
        multi_fwd = {}
        for fd in decay_periods:
            if fd == forward_days:
                multi_fwd[fd] = fwd_returns
            else:
                multi_fwd[fd] = get_or_compute_forward_returns(
                    mf, dates, forward_days=fd,
                    stock_codes=stock_codes,
                    start_date='20250101', end_date='20250620',
                )
        decay = ic_decay(scores, multi_fwd)

    # 8. Top/Bottom
    latest = scores.iloc[-1].dropna().sort_values(ascending=False)
    top20 = latest.head(20)
    bottom20 = latest.tail(20)

    return {
        'scores': scores,
        'ic': ic,
        'qr': qr,
        'decay': decay,
        'top20': top20,
        'bottom20': bottom20,
        'n_stocks': len(stocks),
        'n_dates': len(scores),
        'coverage': scores.notna().sum().mean(),
        'elapsed': 0,
    }


# ── 控制区 ──
with st.expander("⚙️ 运行参数", expanded=True):
    row1 = st.columns(4)
    with row1[0]:
        factor_name = st.selectbox("因子类型", list(FACTOR_MAP.keys()))
        st.caption(FACTOR_MAP[factor_name][1])
    with row1[1]:
        n = st.number_input("参数 n", min_value=5, max_value=250, value=20, step=5)
    with row1[2]:
        forward_days = st.number_input("前向天数", min_value=1, max_value=120, value=20, step=5)
    with row1[3]:
        stock_pool = st.radio("股票池", list(STOCK_POOL.keys()), horizontal=True)

    row2 = st.columns(5)
    with row2[0]:
        normalize = st.checkbox("Z-score 标准化")
    with row2[1]:
        industry_neutral = st.checkbox("行业中性化")
    with row2[2]:
        market_cap_neutral = st.checkbox("市值中性化")
    with row2[3]:
        show_decay = st.checkbox("IC 衰减分析")
    with row2[4]:
        run_btn = st.button("🚀 运行分析", type="primary", use_container_width=True)

# ── session_state 初始化 ──
for key in ['result', 'last_params']:
    if key not in st.session_state:
        st.session_state[key] = None

# ── 运行分析 ──
if run_btn:
    current_params = (factor_name, n, forward_days, stock_pool,
                      normalize, industry_neutral, market_cap_neutral, show_decay)

    with st.spinner(f"正在分析 {factor_name}（{STOCK_POOL[stock_pool]}，{forward_days}日前向）..."):
        t0 = time.time()
        result = run_analysis(*current_params)
        result['elapsed'] = time.time() - t0

    if 'error' in result:
        st.error(f"❌ {result['error']}")
    else:
        st.session_state.result = result
        st.session_state.last_params = current_params

# ── 结果展示 ──
result = st.session_state.result
if result is None:
    st.info("👆 设置因子参数，点击「运行分析」开始评估。默认使用沪深 300 成分股（~277 只，< 5s）。")
elif 'error' in result:
    st.error(f"❌ {result['error']}")
else:
    # 指标卡片
    ic = result['ic']
    st.subheader("📊 因子评估结果")

    cols = st.columns(4)
    with cols[0]:
        ic_val = ic.get('ic_mean')
        delta = "显著" if ic.get('ic_ir', 0) > 0.3 else "弱"
        st.metric("IC 均值", f"{ic_val:.4f}" if ic_val else "N/A", delta=delta)
    with cols[1]:
        st.metric("IC IR", f"{ic.get('ic_ir', 0):.4f}")
    with cols[2]:
        st.metric("IC > 0 占比", f"{ic.get('ic_positive_ratio', 0):.1%}")
    with cols[3]:
        st.metric("平均覆盖率", f"{result['coverage']:.0f} 只/期")

    st.caption(f"股票池: {result['n_stocks']} 只 | 日期: {result['n_dates']} 期 | 耗时: {result['elapsed']:.1f}s")

    # IC 序列图
    if 'ic_series' in ic and ic['ic_series'] is not None:
        st.subheader("📈 IC 序列")
        ic_series = ic['ic_series']
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=ic_series.values,
            mode='lines',
            line=dict(color='#1f77b4', width=1),
            name='IC',
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_hline(y=ic['ic_mean'], line_dash="dot", line_color="green",
                      annotation_text=f"均值 {ic['ic_mean']:.4f}")
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="期数",
            yaxis_title="IC",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # IC 衰减 + 分层收益（并排）
    decay = result.get('decay')
    qr = result.get('qr')

    if decay is not None and not decay.empty:
        col_left, col_right = st.columns(2)
    else:
        col_left = st
        col_right = None

    # IC 衰减
    if decay is not None and not decay.empty:
        with col_left:
            st.subheader("📉 IC 衰减")
            fig = go.Figure()
            colors = ['#1f77b4' if v >= 0 else '#d62728' for v in decay['ic_mean']]
            fig.add_trace(go.Bar(
                x=decay['forward_days'],
                y=decay['ic_mean'],
                marker_color=colors,
                text=[f"{v:.4f}" for v in decay['ic_mean']],
                textposition='outside',
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="前向天数",
                yaxis_title="IC 均值",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # 分层收益
    if qr is not None and not qr.empty:
        target_col = col_right if col_right else st
        with target_col:
            st.subheader("📊 分层收益")
            fig = go.Figure()
            rets = qr['mean_ret'].values
            colors_bar = ['#2ca02c' if v >= 0 else '#d62728' for v in rets]
            fig.add_trace(go.Bar(
                x=qr.index,
                y=rets,
                marker_color=colors_bar,
                text=[f"{v:.2f}%" for v in rets],
                textposition='outside',
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_title="分组",
                yaxis_title="平均收益 (%)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Top 20 / Bottom 20
    st.subheader("🏆 最新一期因子排名")
    col_t, col_b = st.columns(2)

    with col_t:
        st.markdown("**Top 20**")
        top_df = pd.DataFrame({
            '代码': result['top20'].index,
            '因子值': [f"{v:.2f}" for v in result['top20'].values],
        }).reset_index(drop=True)
        st.dataframe(top_df, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("**Bottom 20**")
        bottom_df = pd.DataFrame({
            '代码': result['bottom20'].index,
            '因子值': [f"{v:.2f}" for v in result['bottom20'].values],
        }).reset_index(drop=True)
        st.dataframe(bottom_df, use_container_width=True, hide_index=True)
