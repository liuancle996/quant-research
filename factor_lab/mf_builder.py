"""MF 构建器 — 创建和配置 hikyuu MultiFactor 评分板

核心职责：
- 定义因子公式 → 创建 MF 评分板
- 设置标准化（Z-score）和中性化（行业/市值）
- 提供股票池过滤（A股 / 排除ST / 排除北证）
"""

from datetime import datetime

from .hikyuu_adapter import (
    sm, constant, Datetime, Query, NO_RECOVER,
    MA, CLOSE, LOG,
    MF_EqualWeight, NORM_Zscore,
)


def get_a_share_universe(exclude_st: bool = True) -> list:
    """获取有效 A 股列表

    Args:
        exclude_st: 是否排除 ST 股票

    Returns:
        Stock 对象列表，已过滤 market in ['SH', 'SZ'], type == STOCKTYPE_A, valid
    """
    stocks = []
    for s in sm.get_stock_list():
        if s.type != constant.STOCKTYPE_A:
            continue
        if not s.valid:
            continue
        if s.market not in ['SH', 'SZ']:
            continue
        if exclude_st and 'ST' in s.name:
            continue
        stocks.append(s)
    stocks.sort(key=lambda s: s.market_code)
    return stocks


def build_mf(
    indicators: list,
    stocks: list = None,
    start_date: str = '20240101',
    end_date: str = None,
    normalize: str = None,
    industry_neutral: bool = False,
    market_cap_neutral: bool = False,
) -> tuple:
    """构建并配置 hikyuu MF 多因子评分板

    Returns:
        (mf, dates): MF_EqualWeight 实例和日期列表
    """
    if stocks is None:
        stocks = get_a_share_universe()

    if end_date is None:
        end_date = '20250620'  # A股数据实际截止日

    query = Query(
        Datetime(int(start_date[:4]), int(start_date[4:6]), int(start_date[6:8])),
        Datetime(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8])),
        'DAY', NO_RECOVER,
    )

    # 参考标的：沪深300
    ref_stk = sm['sh000300']

    mf = MF_EqualWeight(indicators, stocks, query, ref_stk=ref_stk)

    # 标准化
    if normalize == 'zscore':
        if industry_neutral or market_cap_neutral:
            for ind in indicators:
                style_inds = []
                if market_cap_neutral:
                    style_inds.append(LOG(CLOSE()))
                mf.add_special_normalize(
                    ind.name,
                    NORM_Zscore(),
                    category='行业板块' if industry_neutral else '',
                    style_inds=style_inds,
                )
        else:
            mf.set_normalize(NORM_Zscore())

    # 从参考标的 K 线提取日期列表（在 query 范围内）
    ref_k = ref_stk.get_kdata(query)
    dates = [r.datetime for r in ref_k]

    return mf, dates
