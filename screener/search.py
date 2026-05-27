"""
股票搜索模块
============
提供模糊搜索功能，支持按股票代码或名称片段匹配。
"""

from typing import Optional

from screener.hikyuu_adapter import sm, Query, constant


def search_stocks(keyword: str, top_n: int = 20) -> list[dict]:
    """
    模糊搜索股票，按代码或名称匹配。

    Parameters
    ----------
    keyword : str
        搜索关键词。支持: 纯数字代码(000001) / 完整代码(SZ000001) / 名称片段(平安)
    top_n : int, default 20
        最大返回条数。

    Returns
    -------
    list[dict]
        [{"code": str, "name": str, "market": str, "latest_price": float}, ...]
        按相关度排序（代码精确匹配 > 代码前缀 > 代码包含 > 名称包含）。
    """
    if not keyword or not keyword.strip():
        return []

    keyword = keyword.strip().upper()

    stock_list = list(sm.get_stock_list())
    if not stock_list:
        return []

    results = []

    for s in stock_list:
        if s.type != constant.STOCKTYPE_A:
            continue
        if not s.valid:
            continue

        market = s.market             # "SH" / "SZ"
        full_code = s.market_code     # "SH600000" / "SZ000001"
        numeric_code = full_code[len(market):]  # "600000" / "000001"
        name = s.name

        # 计算匹配得分
        score = 0
        if keyword in (full_code, numeric_code):
            score = 100  # 精确代码匹配
        elif full_code.startswith(keyword) or numeric_code.startswith(keyword):
            score = 80   # 代码前缀匹配
        elif keyword in full_code or keyword in numeric_code:
            score = 60   # 代码片段匹配
        elif keyword in name.upper():
            score = 40   # 名称匹配
        else:
            continue

        # 获取最新价
        try:
            k = s.get_kdata(Query(-1))
        except Exception:
            continue

        if len(k) == 0:
            continue

        latest_price = round(float(k[-1].close), 2)

        results.append({
            "code": full_code,
            "name": name,
            "market": market,
            "latest_price": latest_price,
            "_score": score,
        })

    results.sort(key=lambda x: x["_score"], reverse=True)

    for r in results:
        del r["_score"]

    return results[:top_n]
