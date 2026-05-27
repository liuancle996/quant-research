"""
股票详情模块
============
提供单只股票的 K 线图绘制和基本面信息展示。
使用 Plotly 实现交互式日K（可缩放、拖拽），支持 MA5/10/20/60 可选叠加。
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from screener.hikyuu_adapter import sm, Query, constant


def get_stock_info(code: str) -> Optional[dict]:
    """
    获取单只股票的基本信息。

    Parameters
    ----------
    code : str
        股票代码，如 'sz000001' 或 'SH600000' (大小写不敏感)

    Returns
    -------
    dict or None
        {
            "code": "000001",
            "market": "SZ",
            "name": "平安银行",
            "latest_price": 12.34,
            "pct_change": 1.23,
            "volume": 12345678,
            "valid": True,
        }
        如果股票不存在返回 None。
    """
    try:
        s = sm[code]
    except Exception:
        return None

    if s is None or not s.valid:
        return None

    # 取最近交易日数据
    k = s.get_kdata(Query(-1))
    if len(k) == 0:
        return None

    last = k[-1]
    latest_price = float(last.close)

    # 计算日内涨跌幅（需要前一日收盘价）
    k2 = s.get_kdata(Query(-2))
    pct_change = 0.0
    if len(k2) >= 2:
        prev_close = float(k2[0].close)
        if prev_close > 0:
            pct_change = round((latest_price / prev_close - 1.0) * 100.0, 2)

    return {
        "code": s.market_code,
        "market": s.market,
        "name": s.name,
        "latest_price": latest_price,
        "pct_change": pct_change,
        "volume": int(last.volume),
        "valid": True,
    }


def get_kline_data(code: str, lookback: int = 120) -> Optional[pd.DataFrame]:
    """
    获取股票 K 线数据，返回 DataFrame。

    Parameters
    ----------
    code : str
        股票代码。
    lookback : int, default 120
        回看交易日数。

    Returns
    -------
    pd.DataFrame or None
        包含 open, high, low, close, volume, datetime 列。
    """
    try:
        s = sm[code]
    except Exception:
        return None

    if s is None or not s.valid:
        return None

    k = s.get_kdata(Query(-lookback))
    if len(k) == 0:
        return None

    records = []
    for i in range(len(k)):
        d = k[i]
        records.append({
            "datetime": str(d.datetime)[:10],
            "open": float(d.open),
            "high": float(d.high),
            "low": float(d.low),
            "close": float(d.close),
            "volume": int(d.volume),
        })

    df = pd.DataFrame(records)
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


def calc_ma(df: pd.DataFrame, period: int) -> pd.Series:
    """计算移动平均线。"""
    return df["close"].rolling(window=period).mean()


def plot_kline(
    df: pd.DataFrame,
    mas: Optional[list[int]] = None,
    title: str = "",
) -> go.Figure:
    """
    用 Plotly 绘制交互式日 K 线图 + 成交量柱 + 可选均线。

    Parameters
    ----------
    df : pd.DataFrame
        包含 open/high/low/close/volume/datetime 列。
    mas : list[int], optional
        要显示均线的周期列表，如 [5, 10, 20, 60]。
    title : str, default ""
        图表标题。

    Returns
    -------
    plotly.graph_objects.Figure
    """
    if mas is None:
        mas = [5, 10, 20, 60]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    # ── K 线 ──
    fig.add_trace(
        go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="日K",
            increasing_line_color="red",
            decreasing_line_color="green",
        ),
        row=1,
        col=1,
    )

    # ── 均线 ──
    ma_colors = {5: "#FF9800", 10: "#2196F3", 20: "#9C27B0", 60: "#4CAF50"}
    for p in mas:
        ma_values = calc_ma(df, p)
        color = ma_colors.get(p, "#666666")
        fig.add_trace(
            go.Scatter(
                x=df["datetime"],
                y=ma_values,
                mode="lines",
                name=f"MA{p}",
                line=dict(color=color, width=1.2),
            ),
            row=1,
            col=1,
        )

    # ── 成交量柱 ──
    vol_colors = [
        "red" if row.close >= row.open else "green"
        for _, row in df.iterrows()
    ]
    fig.add_trace(
        go.Bar(
            x=df["datetime"],
            y=df["volume"],
            name="成交量",
            marker_color=vol_colors,
            opacity=0.6,
        ),
        row=2,
        col=1,
    )

    # ── 布局 ──
    fig.update_layout(
        title=dict(text=title, x=0.5),
        xaxis_rangeslider_visible=False,
        height=600,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)

    return fig


def format_volume(vol: int) -> str:
    """格式化成交量显示。"""
    if vol >= 1_0000_0000:
        return f"{vol / 1_0000_0000:.2f}亿"
    elif vol >= 1_0000:
        return f"{vol / 1_0000:.2f}万"
    return str(vol)
