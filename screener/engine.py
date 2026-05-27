"""
筛选引擎
========
screen() 函数：基于 hikyuu 数据的股票筛选核心逻辑。
纯逻辑，无 UI 依赖，返回 pd.DataFrame。
"""

import logging
from typing import Optional

import pandas as pd

from screener.hikyuu_adapter import sm, Query, constant

logger = logging.getLogger(__name__)


# ── 步骤 1：候选池 ─────────────────────────────────────────

def _get_candidates(
    markets: list[str],
    block_category: Optional[str] = None,
    block_name: Optional[str] = None,
) -> list:
    """遍历 StockManager，返回符合条件的 A 股列表。

    当指定 block_category + block_name 时，仅从该板块取股票。
    """
    if block_category and block_name:
        from screener.blocks import get_block_stocks

        stocks = get_block_stocks(block_category, block_name)
        candidates = []
        for s in stocks:
            if s.type != constant.STOCKTYPE_A:
                continue
            if not s.valid:
                continue
            if s.market not in markets:
                continue
            candidates.append(s)
        return candidates

    stock_list = list(sm.get_stock_list())
    if not stock_list:
        raise RuntimeError(
            "hikyuu StockManager 未加载数据。请检查 ~/.hikyuu/hikyuu.ini 配置。"
        )

    candidates = []
    for s in stock_list:
        if s.type != constant.STOCKTYPE_A:
            continue
        if not s.valid:
            continue
        if s.market not in markets:
            continue
        candidates.append(s)

    return candidates


# ── 步骤 2：逐只计算 + 过滤 ──────────────────────────────

def _calc_and_filter(
    candidates: list,
    lookback_days: int,
    min_pct: Optional[float],
    max_pct: Optional[float],
    min_volume: Optional[int],
    exclude_st: bool,
) -> tuple[list[dict], dict]:
    """对候选池逐只计算指标，返回通过过滤的结果列表和跳过统计。"""
    results: list[dict] = []
    skipped = {"no_data": 0, "too_few": 0, "st": 0, "pct": 0, "vol": 0}

    for s in candidates:
        if exclude_st and "ST" in s.name:
            skipped["st"] += 1
            continue

        try:
            k = s.get_kdata(Query(-lookback_days))
        except Exception:
            skipped["no_data"] += 1
            continue

        n = len(k)
        if n < 2:
            skipped["too_few"] += 1
            continue

        start_price = float(k[0].close)
        end_price = float(k[-1].close)
        pct_change = (end_price / start_price - 1.0) * 100.0

        if min_pct is not None and pct_change < min_pct:
            skipped["pct"] += 1
            continue
        if max_pct is not None and pct_change > max_pct:
            skipped["pct"] += 1
            continue

        volumes = [float(r.volume) for r in k]
        avg_volume = int(sum(volumes) / n)
        latest_volume = int(volumes[-1])

        if min_volume is not None and avg_volume < min_volume:
            skipped["vol"] += 1
            continue

        results.append({
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
        })

    return results, skipped


# ── 步骤 3：排序 + Top-N ──────────────────────────────────

def _sort_and_top(
    results: list[dict],
    sort_by: str,
    ascending: bool,
    top_n: int,
) -> pd.DataFrame:
    """排序并截取 Top-N，返回 DataFrame。"""
    df = pd.DataFrame(results)
    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=ascending).reset_index(drop=True)
    else:
        logger.warning(f"排序字段 '{sort_by}' 不存在，使用默认排序。")
    return df.head(top_n).reset_index(drop=True)


# ── 主入口 ────────────────────────────────────────────────

_COLUMNS = [
    "code", "name", "market", "latest_price",
    "start_price", "end_price", "pct_change",
    "avg_volume", "latest_volume", "n_days",
]


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
    block_category: Optional[str] = None,
    block_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    A股筛选主函数。

    Parameters
    ----------
    markets : list[str], default ["SH", "SZ"]
        交易所列表。可选值: "SH"(上证), "SZ"(深证), "BJ"(北证)
    lookback_days : int, default 20
        回看交易日数。
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
        排序字段。
    ascending : bool, default False
        True=升序, False=降序。
    block_category : str or None, default None
        板块分类。'行业板块' / '概念板块'。指定后仅从该板块筛选。
    block_name : str or None, default None
        板块名称。'半导体' / '保险' 等。需与 block_category 同时指定。

    Returns
    -------
    pd.DataFrame
    """
    if markets is None:
        markets = ["SH", "SZ"]

    candidates = _get_candidates(markets, block_category, block_name)
    results, skipped = _calc_and_filter(
        candidates, lookback_days, min_pct, max_pct, min_volume, exclude_st,
    )

    if not results:
        logger.info("筛选结果为空。请尝试放宽筛选条件。")
        return pd.DataFrame(columns=_COLUMNS)

    df = _sort_and_top(results, sort_by, ascending, top_n)

    logger.info(
        f"筛选完成: 候选池={len(candidates)}, "
        f"跳过ST={skipped['st']}, 无数据={skipped['no_data']}, "
        f"K线不足={skipped['too_few']}, 涨幅过滤={skipped['pct']}, "
        f"成交量过滤={skipped['vol']}, 返回={len(df)}"
    )
    return df
