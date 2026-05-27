"""
板块查询模块
============
提供板块列表、板块内股票、热门板块 Top N 查询。
基于 hikyuu 板块系统（行业 86 / 概念 435 / 指数 187 / 地域 31）。
"""

import logging
from typing import Optional

from screener.hikyuu_adapter import sm, Query

logger = logging.getLogger(__name__)


def get_block_list(category: str) -> list[dict]:
    """
    返回某分类下所有板块列表。

    Parameters
    ----------
    category : str
        板块分类。'行业板块' / '概念板块' / '指数板块' / '地域板块'

    Returns
    -------
    list[dict]
        [{"name": str, "stock_count": int}, ...]
    """
    results = []
    try:
        all_blocks = sm.get_block_list()
        for b in all_blocks:
            if b.category == category:
                count = sum(1 for _ in b)
                results.append({"name": b.name, "stock_count": count})
    except Exception as e:
        logger.warning(f"获取板块列表失败 (category={category}): {e}")
        return []

    results.sort(key=lambda x: x["name"])
    return results


def get_block_stocks(category: str, name: str) -> list:
    """
    返回板块内股票列表（hikyuu Stock 对象）。

    Parameters
    ----------
    category : str
        板块分类。
    name : str
        板块名称。

    Returns
    -------
    list
        hikyuu Stock 对象列表。
    """
    try:
        b = sm.get_block(category, name)
        if b is None:
            return []
        return list(b)
    except Exception as e:
        logger.warning(f"获取板块股票失败 (category={category}, name={name}): {e}")
        return []


def get_top_blocks(
    n: int = 5,
    category: str = "行业板块",
    exclude_st: bool = True,
) -> list[dict]:
    """
    按板块内股票平均涨跌幅排序，返回 Top N 板块。

    Parameters
    ----------
    n : int, default 5
        返回前 N 个板块。
    category : str, default "行业板块"
        板块分类。
    exclude_st : bool, default True
        是否排除 ST 股票。

    Returns
    -------
    list[dict]
        [{"name": str, "avg_pct": float, "stock_count": int, "up_count": int,
          "down_count": int}, ...]
        按 avg_pct 降序排列。
    """
    blocks = get_block_list(category)
    results = []

    for blk in blocks:
        block_name = blk["name"]
        stocks = get_block_stocks(category, block_name)
        if not stocks:
            continue

        pct_list = []
        for s in stocks:
            if not s.valid:
                continue
            if exclude_st and "ST" in s.name:
                continue
            try:
                k = s.get_kdata(Query(-2))
            except Exception:
                continue
            if len(k) < 2:
                continue
            prev = float(k[0].close)
            cur = float(k[-1].close)
            if prev == 0:
                continue
            pct = round((cur / prev - 1.0) * 100.0, 2)
            pct_list.append(pct)

        if not pct_list:
            continue

        avg_pct = round(sum(pct_list) / len(pct_list), 2)
        up_count = sum(1 for p in pct_list if p > 0)
        down_count = sum(1 for p in pct_list if p < 0)

        results.append({
            "name": block_name,
            "avg_pct": avg_pct,
            "stock_count": len(pct_list),
            "up_count": up_count,
            "down_count": down_count,
        })

    results.sort(key=lambda x: x["avg_pct"], reverse=True)
    return results[:n]


def get_block_summary(
    category: str = "行业板块",
    name: str = "银行",
    lookback_days: int = 2,
) -> Optional[dict]:
    """
    获取单个板块的汇总信息（平均涨跌幅、上涨下跌股票数等）。

    Parameters
    ----------
    category : str
        板块分类。
    name : str
        板块名称。
    lookback_days : int, default 2
        计算涨跌幅的回看天数（通常为 2，即昨天到今天的涨跌幅）。

    Returns
    -------
    dict or None
        {"name": str, "category": str, "stock_count": int, "avg_pct": float,
         "up_count": int, "down_count": int}
    """
    stocks = get_block_stocks(category, name)
    if not stocks:
        return None

    pct_list = []
    for s in stocks:
        if not s.valid:
            continue
        try:
            k = s.get_kdata(Query(-lookback_days))
        except Exception:
            continue
        if len(k) < 2:
            continue
        prev = float(k[0].close)
        cur = float(k[-1].close)
        if prev == 0:
            continue
        pct = round((cur / prev - 1.0) * 100.0, 2)
        pct_list.append(pct)

    if not pct_list:
        return None

    return {
        "name": name,
        "category": category,
        "stock_count": len(pct_list),
        "avg_pct": round(sum(pct_list) / len(pct_list), 2),
        "up_count": sum(1 for p in pct_list if p > 0),
        "down_count": sum(1 for p in pct_list if p < 0),
    }
