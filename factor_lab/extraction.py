"""评分提取层 — 从 hikyuu MF 提取因子评分和未来收益为 pandas DataFrame

支持 forward returns 缓存：首次计算后存为 parquet，后续因子切换秒出结果。
"""

import hashlib
import json
import numpy as np
import pandas as pd
from pathlib import Path

from .hikyuu_adapter import sm, Query

# 缓存目录
CACHE_DIR = Path(__file__).resolve().parent / 'cache'


def extract_scores(mf: "MF_EqualWeight", dates: list) -> pd.DataFrame:
    """从 MF 提取所有日期的因子评分为 DataFrame

    优化：用 to_np() 替代 iterrows()，避免逐行 DataFrame 索引开销。
    """
    all_scores = mf.get_all_scores()
    n = min(len(all_scores), len(dates))

    pd_dates = [pd.Timestamp(str(dates[i])) for i in range(n)]

    # 第一批：收集所有股票代码
    all_codes = set()
    for i in range(n):
        for item in all_scores[i].to_np():
            all_codes.add(item[0])
    all_codes = sorted(all_codes)

    # 第二批：构建评分矩阵 (date × stock)
    # 使用 numpy 数组填充，最后转 DataFrame（比逐行 loc 赋值快 10x+）
    code_to_col = {code: j for j, code in enumerate(all_codes)}
    m = len(all_codes)
    mat = np.full((n, m), np.nan, dtype=np.float64)

    for i in range(n):
        for item in all_scores[i].to_np():
            code, _, score = item
            if score is not None and not (isinstance(score, float) and np.isnan(score)):
                j = code_to_col[code]
                mat[i, j] = float(score)

    result = pd.DataFrame(mat, index=pd_dates, columns=all_codes)
    result.index.name = 'date'
    return result


def extract_forward_returns(
    mf: "MF_EqualWeight",
    dates: list,
    forward_days: int = 20,
) -> pd.DataFrame:
    """提取未来收益率矩阵

    对每个日期，计算每只股票 forward_days 后的收益率。
    使用字典查找实现 O(1) 日期定位。

    Args:
        mf: MF 实例
        dates: 日期列表
        forward_days: 前向天数

    Returns:
        DataFrame: date × stock，值为 forward_days 后的收益率
    """
    all_scores = mf.get_all_scores()
    n = min(len(all_scores), len(dates))

    if n == 0:
        return pd.DataFrame()

    dates_used = dates[:n]

    # 收集所有股票代码
    stock_codes = set()
    for i in range(n):
        for item in all_scores[i].to_np():
            stock_codes.add(item[0])
    stock_codes = list(stock_codes)

    # 预先建立日期到索引的查找表
    date_to_idx = {d: i for i, d in enumerate(dates_used)}

    returns = {}
    for code in stock_codes:
        try:
            s = sm[code]
        except Exception:
            continue

        k = s.get_kdata(Query(-n * 3))
        if len(k) < 2:
            continue

        close_prices = np.array([r.close for r in k], dtype=np.float64)
        k_date_to_idx = {r.datetime: i for i, r in enumerate(k)}

        for d in dates_used:
            idx = k_date_to_idx.get(d)
            if idx is None:
                continue
            future_idx = idx + forward_days
            if future_idx < len(close_prices) and close_prices[idx] > 0:
                ret = (close_prices[future_idx] / close_prices[idx]) - 1.0
                if code not in returns:
                    returns[code] = {}
                # 用字符串键，避免 hikyuu Datetime 与 pd.Timestamp 类型不匹配
                returns[code][pd.Timestamp(str(d))] = ret

    pd_dates = [pd.Timestamp(str(d)) for d in dates_used]
    result = pd.DataFrame(returns, index=pd_dates)
    result.index.name = 'date'
    return result


def _cache_key(stock_codes: list, start_date: str, end_date: str, forward_days: int) -> str:
    """生成缓存键，基于股票池 + 日期范围 + 前向天数"""
    key_data = json.dumps({
        'codes': sorted(stock_codes),
        'start': start_date,
        'end': end_date,
        'fwd': forward_days,
    }, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()[:16]


def get_or_compute_forward_returns(
    mf: "MF_EqualWeight",
    dates: list,
    forward_days: int = 20,
    stock_codes: list = None,
    start_date: str = '',
    end_date: str = '',
    force_recompute: bool = False,
) -> pd.DataFrame:
    """获取前向收益矩阵，优先从缓存加载

    首次计算耗时 ~60-80s（3000 只股票），缓存后加载 < 2s。

    Args:
        mf: MF 实例
        dates: 日期列表
        forward_days: 前向天数
        stock_codes: 股票代码列表（用于缓存键）
        start_date: 起始日期（用于缓存键）
        end_date: 结束日期（用于缓存键）
        force_recompute: 强制重新计算
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if stock_codes is None:
        all_scores = mf.get_all_scores()
        n = min(len(all_scores), len(dates))
        codes_set = set()
        for i in range(n):
            for item in all_scores[i].to_np():
                codes_set.add(item[0])
        stock_codes = list(codes_set)

    key = _cache_key(stock_codes, start_date, end_date, forward_days)
    cache_path = CACHE_DIR / f'fwd_{key}.parquet'

    if not force_recompute and cache_path.exists():
        result = pd.read_parquet(cache_path)
        pd_dates = [pd.Timestamp(str(d)) for d in dates[:min(len(mf.get_all_scores()), len(dates))]]
        result = result[result.index.isin(pd_dates)]
        return result

    result = extract_forward_returns(mf, dates, forward_days)
    if not result.empty:
        result.to_parquet(cache_path)

    return result
