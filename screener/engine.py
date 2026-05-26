"""
筛选引擎
========
screen() 函数：基于 hikyuu 数据的股票筛选核心逻辑。
纯逻辑，无 UI 依赖，返回 pd.DataFrame。
"""

import logging
from typing import Optional

import pandas as pd

from .hikyuu_adapter import sm, Query, constant

logger = logging.getLogger(__name__)


def screen(
    markets: Optional[list[str]] = None,
    lookback_days: int = 20,
    min_pct: Optional[float] = None,
    max_pct: Optional[float] = None,
    min_volume: Optional[int] = None,
    exclude_st: bool = True,
    top_n: int = 50,
    sort_by: str = "pct_change",
    ascending: bool = False,
) -> pd.DataFrame:
    """
    A股筛选主函数。

    Parameters
    ----------
    markets : list[str], default ["SH", "SZ"]
        交易所列表。可选值: "SH"(上证), "SZ"(深证), "BJ"(北证)
    lookback_days : int, default 20
        回看交易日数。K 线取最近 N 条日线。
    min_pct : float or None, default None
        最小涨幅(%)。None = 不限。
    max_pct : float or None, default None
        最大涨幅(%)。None = 不限。
    min_volume : int or None, default None
        最小日均成交量(股)。None = 不限。
    exclude_st : bool, default True
        是否排除名称含 "ST" 的股票。
    top_n : int, default 50
        返回前 N 只股票。
    sort_by : str, default "pct_change"
        排序字段。可选: "pct_change", "volume", "avg_volume", "latest_price", "code", "name"
    ascending : bool, default False
        True=升序, False=降序。

    Returns
    -------
    pd.DataFrame
        包含 10 列的结果表：code, name, market, latest_price,
        start_price, end_price, pct_change, avg_volume,
        latest_volume, n_days

    Raises
    ------
    RuntimeError
        hikyuu 初始化失败（StockManager 为空）。
    """
    if markets is None:
        markets = ["SH", "SZ"]

    # --- 步骤 1：获取候选池 ---
    all_stocks = sm.get_stock_list()
    if len(all_stocks) == 0:
        raise RuntimeError("hikyuu StockManager 未加载数据。请检查 ~/.hikyuu/hikyuu.ini 配置。")

    results: list[dict] = []
    skipped_no_data = 0
    skipped_too_few = 0
    skipped_st = 0
    skipped_pct = 0
    skipped_vol = 0

    for s in all_stocks:
        # 过滤：A股类型
        if s.type != constant.STOCKTYPE_A:
            continue
        # 过滤：有效状态
        if not s.valid:
            continue
        # 过滤：交易所
        if s.market not in markets:
            continue
        # 过滤：ST（基于名称）
        if exclude_st and "ST" in s.name:
            skipped_st += 1
            continue

        # --- 步骤 2：逐只计算指标 ---
        try:
            k = s.get_kdata(Query(-lookback_days))
        except Exception:
            # 某些股票可能无 K 线数据（如刚上市但无历史）
            skipped_no_data += 1
            continue

        n = len(k)
        if n < 2:
            skipped_too_few += 1
            continue

        start_price = float(k[0].close)
        end_price = float(k[-1].close)

        # 计算涨跌幅
        pct_change = (end_price / start_price - 1.0) * 100.0

        # 涨跌幅过滤
        if min_pct is not None and pct_change < min_pct:
            skipped_pct += 1
            continue
        if max_pct is not None and pct_change > max_pct:
            skipped_pct += 1
            continue

        # 成交量计算
        volumes = [float(r.volume) for r in k]
        avg_volume = int(sum(volumes) / n)
        latest_volume = int(volumes[-1])

        # 成交量过滤
        if min_volume is not None and avg_volume < min_volume:
            skipped_vol += 1
            continue

        results.append(
            {
                "code": s.market_code,
                "name": s.name,
                "market": s.market,
                "latest_price": round(end_price, 2),
                "start_price": round(start_price, 2),
                "end_price": round(end_price, 2),
                "pct_change": round(pct_change, 2),
                "avg_volume": avg_volume,
                "latest_volume": latest_volume,
                "n_days": n,
            }
        )

    # --- 步骤 3：排序并截取 ---
    if not results:
        logger.info("筛选结果为空。请尝试放宽筛选条件。")
        return pd.DataFrame(
            columns=[
                "code", "name", "market", "latest_price",
                "start_price", "end_price", "pct_change",
                "avg_volume", "latest_volume", "n_days",
            ]
        )

    df = pd.DataFrame(results)

    # 验证排序字段存在
    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=ascending).reset_index(drop=True)
    else:
        logger.warning(f"排序字段 '{sort_by}' 不存在，使用默认排序。")

    df = df.head(top_n).reset_index(drop=True)

    logger.info(
        f"筛选完成: 原始池={len(all_stocks)}, "
        f"跳过ST={skipped_st}, 无数据={skipped_no_data}, "
        f"K线不足={skipped_too_few}, 涨幅过滤={skipped_pct}, "
        f"成交量过滤={skipped_vol}, 返回={len(df)}"
    )

    return df
