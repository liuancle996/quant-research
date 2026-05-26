#!/usr/bin/env python3
"""A股行情筛选器 — 命令行入口

使用:
    # 近一个月上涨的股票（沪深主板+创业板+科创板）
    python run_screener.py --period 1m --min-pct 5

    # 近一年上涨的股票，只看上交所
    python run_screener.py --period 1y --exchange SH

    # 近一周涨幅前30
    python run_screener.py --period 1w --top 30

    # 近三月涨幅10%~30%的股票
    python run_screener.py --period 3m --min-pct 10 --max-pct 30
"""

import argparse
import sys
from pathlib import Path

# 确保 scaffold 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant_data.screener import screen_stocks

EXCHANGE_MAP = {
    "SH": ["SH"],              # 上交所主板
    "SH_ALL": ["SH", "SH_STAR"],  # 上交所主板+科创板
    "SZ": ["SZ"],              # 深交所主板
    "SZ_ALL": ["SZ", "SZ_GEM"],     # 深交所主板+创业板
    "HS": ["SH", "SZ"],        # 沪深主板
    "HS_ALL": ["SH", "SH_STAR", "SZ", "SZ_GEM"],  # 沪深全部
    "BJ": ["BJ"],              # 北交所
}


def main():
    parser = argparse.ArgumentParser(description="A股行情筛选器")
    parser.add_argument(
        "--period", "-p", default="1m",
        choices=["1w", "2w", "1m", "3m", "6m", "1y"],
        help="时间周期：1w=一周, 2w=两周, 1m=一月, 3m=三月, 6m=半年, 1y=一年"
    )
    parser.add_argument("--exchange", "-e", default="HS_ALL",
                        choices=list(EXCHANGE_MAP.keys()),
                        help="交易所：SH=上交所, SZ=深交所, HS=沪深主板, HS_ALL=沪深全部, BJ=北交所")
    parser.add_argument("--min-pct", type=float, default=None,
                        help="最小涨幅(%%)，不设则返回所有")
    parser.add_argument("--max-pct", type=float, default=None,
                        help="最大涨幅(%%)，排除涨幅过大的")
    parser.add_argument("--top", type=int, default=50,
                        help="返回前N只股票")
    args = parser.parse_args()

    exchanges = EXCHANGE_MAP[args.exchange]

    print(f"\n{'='*60}")
    print(f"A股行情筛选器")
    print(f"交易所: {args.exchange} ({', '.join(exchanges)})")
    print(f"时间周期: {args.period}")
    print(f"涨幅范围: {args.min_pct or '不限'} ~ {args.max_pct or '不限'} %%")
    print(f"返回前 {args.top} 只")
    print(f"{'='*60}\n")

    result = screen_stocks(
        exchanges=exchanges,
        period=args.period,
        min_pct=args.min_pct,
        max_pct=args.max_pct,
        top_n=args.top,
    )

    if result.empty:
        print("\n没有符合条件的股票，试试放宽条件。")
    else:
        print(f"\n✅ 共筛选出 {len(result)} 只股票")


if __name__ == "__main__":
    main()
