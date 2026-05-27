"""因子公式定义 — 可复用的因子构建函数

每个函数返回一个配置好的 hikyuu Indicator，设置 .name 后即可作为 MF 的因子输入。
"""

from ..hikyuu_adapter import MA, CLOSE, ROC, STD, HHV, LLV, REF, VOL


def momentum(n: int = 20) -> "Indicator":
    """动量因子：过去 N 日收益率

    ROC(n) = (close_today - close_N_days_ago) / close_N_days_ago × 100
    """
    ind = ROC(CLOSE(), n)
    ind.name = f'动量_{n}日'
    return ind


def volatility(n: int = 20) -> "Indicator":
    """波动率因子：过去 N 日收益率标准差

    STD(ROC(1), n) — 每日收益率的标准差
    """
    daily_ret = ROC(CLOSE(), 1)
    ind = STD(daily_ret, n)
    ind.name = f'波动率_{n}日'
    return ind


def price_position(n: int = 60) -> "Indicator":
    """价格位置因子：(close - low_N) / (high_N - low_N)

    当前价格在过去 N 日高低点区间中的位置，0-1 之间。
    接近 1 = 近期高点，接近 0 = 近期低点。
    """
    c = CLOSE()
    h = HHV(c, n)
    l = LLV(c, n)
    ind = (c - l) / (h - l + 1e-10)
    ind.name = f'价格位置_{n}日'
    return ind


def volume_ratio(n: int = 5, m: int = 20) -> "Indicator":
    """量比因子：短期均量 / 长期均量"""
    short_vol = MA(VOL(), n)
    long_vol = MA(VOL(), m)
    ind = short_vol / (long_vol + 1e-10)
    ind.name = f'量比_{n}_{m}'
    return ind
