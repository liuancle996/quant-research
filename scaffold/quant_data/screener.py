"""A股筛选器 — 按交易所、涨幅、时间区间筛选股票"""

from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .providers.akshare_provider import AkshareProvider

provider = AkshareProvider()


@dataclass
class StockScreener:
    """
    A股筛选器

    使用示例:
        screener = StockScreener()
        result = screener.screen(
            exchanges=["SH", "SZ"],          # 沪深两市
            min_pct_change=10,                # 涨幅 >= 10%
            lookback_days=30,                 # 最近30天（约1个月）
            min_volume=100000,                # 日均成交量 >= 10万手（过滤僵尸股）
        )
    """

    exchanges: list[str] = field(default_factory=lambda: ["SH", "SZ", "SZ_GEM", "SH_STAR"])
    lookback_days: int = 30
    min_pct_change: Optional[float] = None
    max_pct_change: Optional[float] = None
    min_volume: Optional[int] = None
    top_n: int = 50

    def screen(
        self,
        exchanges: Optional[list[str]] = None,
        lookback_days: Optional[int] = None,
        min_pct_change: Optional[float] = None,
        max_pct_change: Optional[float] = None,
        min_volume: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        筛选股票

        参数:
            exchanges: 交易所列表，如 ["SH", "SZ"]。支持 SH/SH_STAR/SZ/SZ_GEM/BJ
            lookback_days: 回看天数，30=近一个月，250≈近一年
            min_pct_change: 最小涨幅(%)
            max_pct_change: 最大涨幅(%)，用于排除涨幅过大的
            min_volume: 最小日均成交量(手)，过滤流动性差的股票
            top_n: 返回前 N 只，按涨幅降序
        """
        exchanges = exchanges or self.exchanges
        lookback_days = lookback_days or self.lookback_days
        min_pct_change = min_pct_change if min_pct_change is not None else self.min_pct_change
        max_pct_change = max_pct_change if max_pct_change is not None else self.max_pct_change
        min_volume = min_volume if min_volume is not None else self.min_volume
        top_n = top_n or self.top_n

        end_date = date.today().strftime("%Y%m%d")
        # 多取一些交易日数据以应对非交易日
        start_date = (date.today() - timedelta(days=lookback_days + 30)).strftime("%Y%m%d")

        # 1. 获取股票列表并分类交易所
        stock_list = provider.get_stock_list()
        stock_list["exchange"] = stock_list["code"].apply(provider.classify_exchange)
        stock_list = stock_list[stock_list["exchange"].isin(exchanges)]

        print(f"交易所筛选后: {len(stock_list)} 只股票")
        print(f"开始逐只获取行情数据（回看 {lookback_days} 天）...")

        results = []
        total = len(stock_list)
        for i, (_, row) in enumerate(stock_list.iterrows()):
            code = row["code"]
            name = row["name"]

            if i % 200 == 0:
                print(f"  进度: {i}/{total} ({i/total*100:.1f}%)")

            try:
                df = provider.get_stock_daily(code, start_date=start_date, end_date=end_date)
                if df.empty or len(df) < 2:
                    continue

                # 取最近 lookback_days 个交易日
                df = df.tail(lookback_days + 1)  # +1 for start price

                start_price = df.iloc[0]["close"]
                end_price = df.iloc[-1]["close"]

                if start_price <= 0:
                    continue

                pct_change = (end_price - start_price) / start_price * 100

                # 涨幅过滤
                if min_pct_change is not None and pct_change < min_pct_change:
                    continue
                if max_pct_change is not None and pct_change > max_pct_change:
                    continue

                # 成交量过滤
                avg_volume = df["volume"].tail(lookback_days).mean()
                if min_volume is not None and avg_volume < min_volume:
                    continue

                results.append({
                    "code": code,
                    "name": name,
                    "exchange": provider.classify_exchange(code),
                    "start_price": round(start_price, 2),
                    "end_price": round(end_price, 2),
                    "pct_change": round(pct_change, 2),
                    "avg_volume": int(avg_volume),
                    "latest_volume": int(df.iloc[-1]["volume"]),
                    "start_date": df.iloc[0]["date"].strftime("%Y-%m-%d"),
                    "end_date": df.iloc[-1]["date"].strftime("%Y-%m-%d"),
                })
            except Exception:
                continue

        print(f"  完成: {total}/{total}")

        result_df = pd.DataFrame(results)
        if result_df.empty:
            print("没有符合条件的股票")
            return result_df

        result_df = result_df.sort_values("pct_change", ascending=False).head(top_n).reset_index(drop=True)
        result_df.index = range(1, len(result_df) + 1)

        print(f"\n筛选结果: {len(result_df)} 只股票")
        return result_df


def screen_stocks(
    exchanges: Optional[list[str]] = None,
    period: str = "1m",
    min_pct: Optional[float] = None,
    max_pct: Optional[float] = None,
    top_n: int = 50,
) -> pd.DataFrame:
    """
    便捷筛选函数

    参数:
        exchanges: 交易所，默认沪深主板+创业板+科创板
        period: 时间周期 — "1w"=1周, "2w"=2周, "1m"=1个月, "3m"=3个月, "6m"=6个月, "1y"=1年
        min_pct: 最小涨幅
        max_pct: 最大涨幅
        top_n: 返回前N只

    返回:
        按涨幅降序排列的 DataFrame
    """
    period_map = {
        "1w": 5, "2w": 10, "1m": 22, "3m": 66, "6m": 132, "1y": 250,
    }
    days = period_map.get(period, 22)

    description = {
        "1w": "最近一周", "2w": "最近两周", "1m": "最近一月",
        "3m": "最近三月", "6m": "最近半年", "1y": "最近一年",
    }

    screener = StockScreener(top_n=top_n)
    result = screener.screen(
        exchanges=exchanges,
        lookback_days=days,
        min_pct_change=min_pct,
        max_pct_change=max_pct,
        min_volume=50000,  # 默认过滤日成交<5万手的
    )

    if not result.empty:
        print(f"\n{description.get(period, period)} 股票涨幅排行 (前{len(result)}只)")
        print("=" * 80)
        for _, row in result.iterrows():
            direction = "↑" if row["pct_change"] > 0 else "↓"
            print(
                f"  {row['code']}  {row['name']:<8s}  "
                f"{row['start_price']:>7.2f} → {row['end_price']:>7.2f}  "
                f"{direction} {abs(row['pct_change']):>6.2f}%  "
                f"日均量:{row['avg_volume']:>10,d}手  "
                f"交易所:{row['exchange']}"
            )

    return result
