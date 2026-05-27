#!/usr/bin/env python3
"""因子实验室 — CLI 入口

用法:
    python -m factor_lab.run                         # 默认：动量因子 20 日，1 年回看
    python -m factor_lab.run momentum --n 60          # 动量因子 60 日
    python -m factor_lab.run momentum --n 20 --forward 10   # 前向 10 天
    python -m factor_lab.run momentum --normalize zscore     # Z-score 标准化
    python -m factor_lab.run momentum --industry-neutral     # 行业中性化
"""

import argparse
import sys
import time
from pathlib import Path

# 确保 factor_lab 在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factor_lab.mf_builder import build_mf, get_a_share_universe
from factor_lab.extraction import extract_scores, get_or_compute_forward_returns
from factor_lab.evaluation import ic_analysis, quantile_returns, ic_decay
from factor_lab.factors import momentum, volatility, price_position, volume_ratio
from factor_lab.hikyuu_adapter import sm


FACTOR_REGISTRY = {
    'momentum': momentum,
    'volatility': volatility,
    'price_position': price_position,
    'volume_ratio': volume_ratio,
}


def _trim_trailing_nan(df, threshold=0.95):
    """修剪 DataFrame 尾部大部分为 NaN 的行（>threshold 比例缺失即删除）"""
    while len(df) > 0 and df.iloc[-1].isna().mean() > threshold:
        df = df.iloc[:-1]
    return df


def run(args):
    t0 = time.time()

    # 1. 构建因子
    print('=' * 60)
    print(f'  因子实验室 — {args.factor} 因子评估')
    print('=' * 60)

    factor_fn = FACTOR_REGISTRY[args.factor]

    # 处理 kwargs：momentum(n=20) 等
    kwargs = {}
    if args.n:
        kwargs['n'] = args.n

    indicator = factor_fn(**kwargs)
    print(f'\n[1/5] 因子: {indicator.name}')

    # 2. 股票池
    stocks = get_a_share_universe()
    print(f'[2/5] 股票池: {len(stocks)} 只 A 股')

    # 3. 构建 MF
    print(f'[3/5] 构建 hikyuu MF 评分板...')
    mf, dates = build_mf(
        [indicator],
        stocks=stocks,
        start_date=args.start,
        end_date=args.end,
        normalize=args.normalize,
        industry_neutral=args.industry_neutral,
        market_cap_neutral=args.market_cap_neutral,
    )

    # 4. 提取评分
    print(f'[4/5] 提取因子评分...')
    scores = extract_scores(mf, dates)

    # 5. 计算 forward returns 并进行评估
    print(f'[5/5] 计算前向收益 + 因子评估...')

    # 收集股票代码（用于缓存键）
    stock_codes = [s.market_code for s in stocks]

    # 单期 forward returns (用于 IC 和分层)，优先从缓存加载
    fwd_returns = get_or_compute_forward_returns(
        mf, dates, forward_days=args.forward,
        stock_codes=stock_codes, start_date=args.start, end_date=args.end,
        force_recompute=args.force_recompute,
    )
    if fwd_returns.empty:
        print('\n❌ 无法计算前向收益，可能数据不足')
        return 1

    # 修剪尾部全 NaN 行（数据覆盖范围之外）
    scores = _trim_trailing_nan(scores)
    fwd_returns = _trim_trailing_nan(fwd_returns)

    # 只保留共同日期
    common_dates = scores.index.intersection(fwd_returns.index)
    scores = scores.loc[common_dates]
    fwd_returns = fwd_returns.loc[common_dates]

    # 多期 forward returns (用于 IC 衰减)
    decay_periods = [1, 5, 10, 20, 30, 60]
    multi_fwd = {}
    if not args.no_decay:
        for fd in decay_periods:
            if fd == args.forward:
                multi_fwd[fd] = fwd_returns
            else:
                multi_fwd[fd] = get_or_compute_forward_returns(
                    mf, dates, forward_days=fd,
                    stock_codes=stock_codes, start_date=args.start, end_date=args.end,
                )

    # === 输出报告 ===
    print('\n' + '=' * 60)
    print('  因子评估报告')
    print('=' * 60)

    # 基本信息
    print(f'\n📊 基本信息')
    print(f'  因子名称:     {indicator.name}')
    print(f'  因子类型:     {args.factor}')
    print(f'  标准化:       {args.normalize or "无"}')
    print(f'  行业中性化:   {"是" if args.industry_neutral else "否"}')
    print(f'  市值中性化:   {"是" if args.market_cap_neutral else "否"}')
    print(f'  股票数:       {scores.shape[1]}')
    print(f'  日期数:       {scores.shape[0]}')
    avg_coverage = scores.notna().sum().mean()
    print(f'  平均覆盖率:   {avg_coverage:.1f} 只/期')
    print(f'  前向天数:     {args.forward} 日')

    # IC 分析
    ic = ic_analysis(scores, fwd_returns)
    if 'error' in ic:
        print(f'\n  ⚠️ IC 分析失败: {ic["error"]}')
    else:
        print(f'\n📈 IC 分析 ({ic["n_periods"]} 期)')
        print(f'  IC 均值:      {ic["ic_mean"]:.4f}')
        print(f'  IC 标准差:    {ic["ic_std"]:.4f}')
        print(f'  IC IR:        {ic["ic_ir"]:.4f}')
        print(f'  IC > 0 占比:  {ic["ic_positive_ratio"]:.1%}')

        # IC 序列摘要
        ic_series = ic['ic_series']
        print(f'  IC 最小值:    {ic_series.min():.4f}')
        print(f'  IC 最大值:    {ic_series.max():.4f}')
        print(f'  最近 5 期 IC: {[round(x, 4) for x in ic_series.tail(5).tolist()]}')

    # IC 衰减
    if not args.no_decay:
        decay = ic_decay(scores, multi_fwd, max_days=60)
        if not decay.empty:
            print(f'\n📉 IC 衰减曲线')
            for _, row in decay.iterrows():
                bar = '█' * max(0, int(abs(row['ic_mean']) * 500))
                print(f'  {row["forward_days"]:>3}日: {row["ic_mean"]:.4f}  {bar}')

    # 分层收益
    qr = quantile_returns(scores, fwd_returns, n_groups=5)
    if not qr.empty:
        print(f'\n📊 分层收益分析 (前向 {args.forward} 日)')
        print(f'  {"组别":<6} {"收益均值":>10} {"标准差":>10} {"t 值":>8} {">0占比":>8}')
        print(f'  {"-" * 48}')
        for idx, row in qr.iterrows():
            print(f'  {idx:<6} {row["mean_ret"]:>8.2f}% {row["std_ret"]:>8.2f}% '
                  f'{row["t_stat"]:>8.2f} {row["positive_ratio"]:>7.1%}')

        # 多空 spread
        if 'Q1' in qr.index and 'Q5' in qr.index:
            spread = qr.loc['Q5', 'mean_ret'] - qr.loc['Q1', 'mean_ret']
            print(f'  {"-" * 48}')
            print(f'  Q5-Q1 spread: {spread:+.2f}%')

    # Top/Bottom 股票（最新一期）
    latest_date = scores.index[-1]
    latest_scores = scores.loc[latest_date].dropna().sort_values(ascending=False)

    print(f'\n🏆 最新一期因子排名 ({str(latest_date)[:10]})')
    print(f'\n  Top 20 (因子值最高):')
    for i, (code, score) in enumerate(latest_scores.head(20).items(), 1):
        name = sm[code].name if code in [s.market_code for s in stocks] else ''
        print(f'  {i:>2}. {code} {name:<8} {score:>10.4f}')

    print(f'\n  Bottom 20 (因子值最低):')
    for i, (code, score) in enumerate(latest_scores.tail(20).items(), 1):
        name = sm[code].name if code in [s.market_code for s in stocks] else ''
        print(f'  {i:>2}. {code} {name:<8} {score:>10.4f}')

    elapsed = time.time() - t0
    print(f'\n⏱️  总耗时: {elapsed:.1f}s')
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='因子实验室 — 基于 hikyuu 的因子评估工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python -m factor_lab.run momentum --n 20
  python -m factor_lab.run momentum --n 60 --forward 10
  python -m factor_lab.run momentum --normalize zscore --industry-neutral
  python -m factor_lab.run volatility --n 20
  python -m factor_lab.run price_position --n 60
        ''',
    )
    parser.add_argument(
        'factor', nargs='?', default='momentum',
        choices=list(FACTOR_REGISTRY.keys()),
        help='因子名称 (默认: momentum)',
    )
    parser.add_argument('--n', type=int, default=20, help='因子参数 n (默认: 20)')
    parser.add_argument('--forward', type=int, default=20, help='前向收益天数 (默认: 20)')
    parser.add_argument('--start', default='20250101', help='起始日期 YYYYMMDD (默认: 20250101)')
    parser.add_argument('--end', default='20250620', help='结束日期 YYYYMMDD (默认: 20250620，A股数据截止日)')
    parser.add_argument('--normalize', choices=['zscore'], default=None, help='标准化方式')
    parser.add_argument('--industry-neutral', action='store_true', help='行业中性化')
    parser.add_argument('--market-cap-neutral', action='store_true', help='市值中性化')
    parser.add_argument('--no-decay', action='store_true', help='跳过 IC 衰减分析（加速）')
    parser.add_argument('--force-recompute', action='store_true', help='强制重新计算 forward returns（忽略缓存）')

    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
