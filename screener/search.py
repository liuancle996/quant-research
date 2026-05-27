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
        搜索关键词（代码片段或名称片段）。
    top_n : int, default 20
        最大返回条数。

    Returns
    -------
    list[dict]
        [{"code": str, "name": str, "market": str, "latest_price": float}, ...]
        按相关度排序（代码精确匹配 > 代码模糊匹配 > 名称匹配）。
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

        code = s.market_code[len(s.market):]  # 纯数字代码 "000001"
        full_code = s.market_code              # "SZ000001" 格式
        name = s.name

        # 计算匹配得分
        score = 0
        if keyword == code:
            score = 100  # 精确代码匹配
        elif code.startswith(keyword):
            score = 80  # 代码前缀匹配
        elif keyword in code:
            score = 60  # 代码模糊匹配
        elif keyword.upper() in name.upper():
            score = 40  # 名称匹配
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
            "market": s.market,
            "latest_price": latest_price,
            "_score": score,
        })

    # 按得分降序排列
    results.sort(key=lambda x: x["_score"], reverse=True)

    # 去掉内部得分字段
    for r in results:
        del r["_score"]

    return results[:top_n]
