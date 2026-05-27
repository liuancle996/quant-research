"""因子评估 — IC 分析、分层收益、IC 衰减

所有函数输入为：
- scores: pd.DataFrame (date × stock)，从 extraction.extract_scores() 获得
- forward_returns: pd.DataFrame (date × stock)，从 extraction.extract_forward_returns() 获得
"""

import numpy as np
import pandas as pd
from scipy import stats


def ic_analysis(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> dict:
    """时间序列 IC 分析

    对每个日期，计算横截面上因子评分与未来收益的 Spearman Rank IC。

    Returns:
        {
            'ic_mean': float,       # IC 均值
            'ic_std': float,        # IC 标准差
            'ic_ir': float,         # Information Ratio = ic_mean / ic_std
            'ic_positive_ratio': float,  # IC > 0 的日期占比
            'n_periods': int,       # 有效期数
            'ic_series': pd.Series, # 每日 IC 序列
        }
    """
    common_dates = scores.index.intersection(forward_returns.index)
    if len(common_dates) < 10:
        return {'error': f'共同日期不足: {len(common_dates)} 期'}

    ic_values = []
    for d in common_dates:
        score_row = scores.loc[d]
        ret_row = forward_returns.loc[d]

        # 取两者都有效的股票
        valid = score_row.notna() & ret_row.notna()
        if valid.sum() < 30:
            continue

        ic, _ = stats.spearmanr(score_row[valid], ret_row[valid])
        if not np.isnan(ic):
            ic_values.append(ic)

    if len(ic_values) < 5:
        return {'error': f'有效 IC 期数不足: {len(ic_values)}'}

    ic_series = pd.Series(ic_values, name='IC')
    ic_mean = ic_series.mean()
    ic_std = ic_series.std()

    return {
        'ic_mean': round(ic_mean, 6),
        'ic_std': round(ic_std, 6),
        'ic_ir': round(ic_mean / ic_std, 4) if ic_std > 0 else 0.0,
        'ic_positive_ratio': round((ic_series > 0).mean(), 4),
        'n_periods': len(ic_series),
        'ic_series': ic_series,
    }


def ic_decay(
    scores: pd.DataFrame,
    forward_returns: dict,
    max_days: int = 60,
    step: int = 5,
) -> pd.DataFrame:
    """IC 衰减分析

    对不同前向周期的 forward returns 分别计算 IC 均值。

    Args:
        scores: 因子评分 DataFrame
        forward_returns: {forward_days: DataFrame} 的字典
        max_days: 最大前向天数
        step: 步长

    Returns:
        DataFrame: columns=['forward_days', 'ic_mean', 'ic_std', 'ic_ir']
    """
    results = []
    for fd in range(step, max_days + 1, step):
        if fd not in forward_returns:
            continue
        ic_result = ic_analysis(scores, forward_returns[fd])
        if 'error' in ic_result:
            continue
        results.append({
            'forward_days': fd,
            'ic_mean': ic_result['ic_mean'],
            'ic_std': ic_result['ic_std'],
            'ic_ir': ic_result['ic_ir'],
        })

    return pd.DataFrame(results)


def quantile_returns(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_groups: int = 5,
) -> pd.DataFrame:
    """分层收益分析

    每期按因子评分分 n_groups 组，计算每组的平均未来收益。

    Args:
        scores: 因子评分
        forward_returns: 未来收益
        n_groups: 分组数（默认 5）

    Returns:
        DataFrame:
            index = group label (Q1..Qn)
            columns = ['mean_ret', 'std_ret', 't_stat', 'positive_ratio']
    """
    common_dates = scores.index.intersection(forward_returns.index)
    if len(common_dates) < 5:
        return pd.DataFrame()

    group_rets = {f'Q{i+1}': [] for i in range(n_groups)}

    for d in common_dates:
        score_row = scores.loc[d]
        ret_row = forward_returns.loc[d]
        valid = score_row.notna() & ret_row.notna()
        if valid.sum() < n_groups * 10:
            continue

        s = score_row[valid]
        r = ret_row[valid]

        try:
            labels = pd.qcut(s, q=n_groups, labels=[f'Q{i+1}' for i in range(n_groups)])
        except ValueError:
            continue

        for group_name in group_rets:
            mask = labels == group_name
            if mask.sum() > 0:
                group_rets[group_name].append(r[mask].mean())

    result = []
    for group_name, rets in group_rets.items():
        if len(rets) < 3:
            continue
        arr = np.array(rets)
        mean_ret = arr.mean()
        std_ret = arr.std()
        result.append({
            'group': group_name,
            'mean_ret': round(mean_ret * 100, 4),
            'std_ret': round(std_ret * 100, 4),
            't_stat': round(mean_ret / (std_ret / np.sqrt(len(arr))) if std_ret > 0 else 0, 4),
            'positive_ratio': round((arr > 0).mean(), 4),
            'n_periods': len(arr),
        })

    df = pd.DataFrame(result)
    if not df.empty:
        df.set_index('group', inplace=True)
    return df


def factor_summary(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_groups: int = 5,
) -> dict:
    """因子综合评估

    一站式返回 IC 分析 + 分层收益 + 基本信息。

    Returns:
        dict with 'ic', 'quantile_returns', 'coverage', 'n_stocks', 'n_dates'
    """
    ic = ic_analysis(scores, forward_returns)
    qr = quantile_returns(scores, forward_returns, n_groups)

    coverage = scores.notna().sum().mean()
    n_stocks = scores.shape[1]
    n_dates = scores.shape[0]

    return {
        'ic': ic,
        'quantile_returns': qr,
        'coverage': round(coverage, 1),
        'n_stocks': n_stocks,
        'n_dates': n_dates,
    }
