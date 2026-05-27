"""
市场统计模块
============
提供三大指数行情、涨幅榜/跌幅榜/成交量榜 Top 10、涨跌分布统计。
"""

import logging
from typing import Optional

import pandas as pd

from screener.hikyuu_adapter import sm, Query, constant

logger = logging.getLogger(__name__)


# ── 指数映射 ───────────────────────────────────────────────

INDEX_MAP = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "沪深300": "sh000300",
    "创业板指": "sz399006",
}


def get_index_card(index_name: str) -> Optional[dict]:
    """
    获取单个指数的最新行情数据卡片。

    Parameters
    ----------
    index_name : str
        指数名称，如 '上证指数', '深证成指', '沪深300', '创业板指'

    Returns
    -------
    dict or None
        {"name": str, "latest": float, "pct_change": float}
    """
    code = INDEX_MAP.get(index_name)
    if code is None:
        return None

    try:
        s = sm[code]
    except Exception:
        return None

    if s is None or not s.valid:
        return None

    k = s.get_kdata(Query(-2))
    if len(k) < 2:
        return None

    prev_close = float(k[0].close)
    latest = float(k[-1].close)
    pct_change = round((latest / prev_close - 1.0) * 100.0, 2)

    return {
        "name": index_name,
        "latest": round(latest, 2),
        "pct_change": pct_change,
    }


def get_all_index_cards() -> list[dict]:
    """获取所有支持的大盘指数行情卡片。"""
    results = []
    # 主要三大指数
    for name in ["上证指数", "深证成指", "沪深300"]:
        card = get_index_card(name)
        if card:
            results.append(card)
    return results


# ── 全市场排名 ─────────────────────────────────────────────


def _market_rank(
    field: str,
    top_n: int = 10,
    ascending: bool = False,
    exclude_st: bool = True,
    markets: Optional[list[str]] = None,
) -> list[dict]:
    """
    全市场按指定字段排名。

    Parameters
    ----------
    field : str
        排序字段。支持: "pct_change"(涨幅), "volume"(成交量)
    top_n : int, default 10
        返回前 N 只。
    ascending : bool, default False
        排序方向。False=降序(从大到小), True=升序(从小到大)
    exclude_st : bool, default True
        是否排除名称含 ST 的股票。
    markets : list[str], optional
        交易所列表。默认 ["SH", "SZ"]。

    Returns
    -------
    list[dict]
        [{"code": str, "name": str, "market": str, "latest_price": float, "value": float}, ...]
    """
    if markets is None:
        markets = ["SH", "SZ"]

    stock_list = list(sm.get_stock_list())
    if not stock_list:
        return []

    results = []
    for s in stock_list:
        if s.type != constant.STOCKTYPE_A:
            continue
        if not s.valid:
            continue
        if s.market not in markets:
            continue
        if exclude_st and "ST" in s.name:
            continue

        try:
            k = s.get_kdata(Query(-2))
        except Exception:
            continue

        if len(k) < 2:
            continue

        prev_close = float(k[0].close)
        latest_close = float(k[-1].close)
        latest_volume = int(k[-1].volume)

        if field == "pct_change":
            if prev_close == 0:
                continue
            value = round((latest_close / prev_close - 1.0) * 100.0, 2)
        elif field == "volume":
            value = latest_volume
        else:
            continue

        results.append({
            "code": s.market_code,
            "name": s.name,
            "market": s.market,
            "latest_price": round(latest_close, 2),
            "value": value,
        })

    # 排序
    results.sort(key=lambda x: x["value"], reverse=not ascending)
    return results[:top_n]


def get_top_gainers(top_n: int = 10) -> list[dict]:
    """获取涨幅榜 Top N。"""
    return _market_rank("pct_change", top_n=top_n, ascending=False)


def get_top_losers(top_n: int = 10) -> list[dict]:
    """获取跌幅榜 Top N。"""
    return _market_rank("pct_change", top_n=top_n, ascending=True)


def get_top_volume(top_n: int = 10) -> list[dict]:
    """获取成交量榜 Top N。"""
    return _market_rank("volume", top_n=top_n, ascending=False)


# ── 涨跌分布统计 ──────────────────────────────────────────


def get_up_down_stats(
    exclude_st: bool = True,
    markets: Optional[list[str]] = None,
) -> dict:
    """
    统计全市场上涨/下跌/平盘家数。

    Parameters
    ----------
    exclude_st : bool, default True
        是否排除 ST。
    markets : list[str], optional
        交易所列表。默认 ["SH", "SZ"]。

    Returns
    -------
    dict
        {"up": int, "down": int, "flat": int, "total": int}
    """
    if markets is None:
        markets = ["SH", "SZ"]

    stock_list = list(sm.get_stock_list())
    up = down = flat = total = 0

    for s in stock_list:
        if s.type != constant.STOCKTYPE_A:
            continue
        if not s.valid:
            continue
        if s.market not in markets:
            continue
        if exclude_st and "ST" in s.name:
            continue

        try:
            k = s.get_kdata(Query(-2))
        except Exception:
            continue

        if len(k) < 2:
            continue

        total += 1
        prev_close = float(k[0].close)
        latest_close = float(k[-1].close)

        if latest_close > prev_close:
            up += 1
        elif latest_close < prev_close:
            down += 1
        else:
            flat += 1

    return {"up": up, "down": down, "flat": flat, "total": total}
