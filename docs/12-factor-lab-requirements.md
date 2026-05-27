# 因子实验室 — 需求对齐文档

> 日期: 2026-05-27
> 版本: v1.0
> 状态: 已交付（CLI 引擎），前端页面待开发

## 一、调研：业界因子研究怎么做 vs 我们怎么做

### 1.1 业界标准流程（alphalens / Barra / 学术规范）

一个完整的因子研究管线包含以下环节：

```
① 因子公式定义
     ↓
② 因子预处理（去极值 → 标准化 → 中性化）
     ↓
③ 横截面评分（每期对所有股票排序打分）
     ↓
④ IC 分析（Rank IC 均值/标准差/IR、IC 序列、IC 衰减）
     ↓
⑤ 分层回测（分 5-10 组，看各组未来收益的单调性）
     ↓
⑥ 换手率分析（因子排名的稳定性）
     ↓
⑦ 因子相关性矩阵（多因子场景）
```

### 1.2 hikyuu 已有的能力（实测验证）

| 环节 | hikyuu 能力 | 实测结果 |
|------|------------|----------|
| 因子定义 | `MA(CLOSE(), 20).name = 'MA20'` — 任何 Indicator 都可以作为因子 | ✓ |
| 批量计算 | `MF_EqualWeight([indicators], stocks, query, ref_stk)` | ✓ 3000只 × 110天，MF 创建 0.0s |
| 标准化 | `mf.set_normalize(NORM_Zscore())` | ✓ 内置 |
| 行业中性化 | `mf.add_special_normalize("factor", NORM_Zscore(), category="行业板块")` | ✓ 内置 |
| 市值中性化 | `mf.add_special_normalize("factor", ..., style_inds=[LOG(CLOSE()*LIUTONGPAN())])` | ✓ 内置 |
| 横截面评分 | `mf.get_scores(date) → DataFrame(market_code, name, score)` | ✓ |

### 1.3 hikyuu 缺失的（因子实验室补齐）

| 缺失环节 | 因子实验室实现 |
|----------|---------------|
| IC 分析报告 | `evaluation.ic_analysis()` — IC 均值/标准差/IR/序列 |
| IC 衰减曲线 | `evaluation.ic_decay()` — forward 1/5/10/20/30/60 天的 IC 变化 |
| 分层收益分析 | `evaluation.quantile_returns()` — 5/10 组收益 + t 值 + 胜率 |
| 评估报告 | `run.py` CLI — 完整文本报告 |

### 1.4 方案对比

| | 原方案 (v0.1) | 最终方案 (v1.0) |
|---|---|---|
| 因子计算 | 自己写 python 循环 | hikyuu MF 系统批量计算（C++ 引擎） |
| 预处理 | 没有 | hikyuu NORM_Zscore + 行业/市值中性化 |
| 评估 | 自己写 IC / 分层 | 从 MF.get_all_scores() 提取 → pandas/ scipy 分析 |
| 性能 | 未知 | 3000 只 110 天 = 21s（MF 计算）+ 评估 < 3s |

## 二、定位与边界

### 2.1 一句话定位

**基于 hikyuu MF 系统的因子评估层** — 利用 hikyuu 的因子计算和预处理能力，补齐 IC 分析、分层收益、衰减分析等评估环节。

### 2.2 能做

- 定义因子 → hikyuu MF 批量计算 + 标准化/中性化 → 提取评分 → IC/分层/衰减分析
- 单因子评估报告：IC 统计 + IC 衰减曲线 + 分层收益 + Top/Bottom 股票
- 4 个内置因子：动量、波动率、价格位置、量比
- 行业中性化 / 市值中性化 一键开关
- forward returns 缓存（parquet），首次 60s → 二次 < 2s

### 2.3 不能做（明确边界）

- 不是策略回测系统 — 不做信号生成、不下单
- 不是多因子组合框架 — 本版只做单因子评估
- 不做分钟线级别因子
- 不做基本面因子

## 三、技术方案

### 3.1 核心架构

```
hikyuu MF 系统（C++ 引擎）
  ├── 因子定义: Indicator → Factor formula
  ├── 批量计算: MF_EqualWeight(stocks, query, ref_stk)
  ├── 预处理: NORM_Zscore + 行业中性化 + 市值中性化
  └── 评分提取: mf.get_all_scores() → ScoreRecordList
           │
           ▼
    factor_lab/（Python 评估层）
  ├── extraction.py: extract_scores() / get_or_compute_forward_returns()
  │                   → pd.DataFrame(date × stock)
  ├── evaluation.py: ic_analysis() / ic_decay() / quantile_returns()
  └── run.py: CLI 入口
```

### 3.2 模块结构（实际交付）

```
factor_lab/
├── __init__.py
├── hikyuu_adapter.py      ← hikyuu 导入 + 环境初始化（LD_PRELOAD, unset proxy）
├── mf_builder.py          ← build_mf() 返回 (mf, dates)；get_a_share_universe()
├── extraction.py          ← extract_scores(mf, dates) → DataFrame
│                           ← get_or_compute_forward_returns() 含 parquet 缓存
├── evaluation.py          ← ic_analysis / ic_decay / quantile_returns / factor_summary
├── factors/__init__.py    ← 4 个因子函数：momentum / volatility / price_position / volume_ratio
├── run.py                 ← CLI：argparse + 报告输出
└── cache/                 ← forward returns parquet 缓存（gitignored）
```

### 3.3 缓存设计

forward returns 只依赖股票池 + 日期范围 + forward_days，不依赖具体因子。缓存键 = MD5(股票代码列表, start, end, forward_days)。

| 场景 | 首次 | 缓存后 |
|------|------|--------|
| 全量 3000 只 + IC 衰减 | 62s | 28s |
| 全量 3000 只 `--no-decay` | 62s | 24s |
| 沪深 300 277 只 | 2.5s | 2.5s |

瓶颈在 hikyuu `get_all_scores()`（C++ 内部计算，21s），非 Python 代码。

### 3.4 CLI 参数

```
python -m factor_lab.run <factor> [options]

factor: momentum | volatility | price_position | volume_ratio
--n N              因子参数（默认 20）
--forward N        前向收益天数（默认 20）
--start YYYYMMDD   起始日期（默认 20250101）
--end YYYYMMDD     结束日期（默认 20250620）
--normalize zscore Z-score 标准化
--industry-neutral  行业中性化
--market-cap-neutral 市值中性化
--no-decay          跳过 IC 衰减分析（加速）
--force-recompute   强制重算 forward returns
```

## 四、性能基准（实测）

| 股票池 | 股票数 | 日期数 | MF 计算 | 评估 | 总计 |
|--------|--------|--------|---------|------|------|
| 全量 A 股 | 3000 | 110 | 21s | 3s | 24s |
| 沪深 300 | 277 | 110 | 2.3s | 0.2s | 2.5s |
| 前 200 只 | 200 | 110 | 1.5s | 0.3s | 4.7s |

## 五、交付物

| 文件 | 说明 | 状态 |
|------|------|------|
| `factor_lab/__init__.py` | 包初始化 | ✅ |
| `factor_lab/hikyuu_adapter.py` | 环境初始化 | ✅ |
| `factor_lab/mf_builder.py` | MF 构建器 + 股票池 | ✅ |
| `factor_lab/extraction.py` | 评分提取 + 缓存 | ✅ |
| `factor_lab/evaluation.py` | IC/分层/衰减 | ✅ |
| `factor_lab/factors/__init__.py` | 4 个内置因子 | ✅ |
| `factor_lab/run.py` | CLI 入口 | ✅ |
| `docs/12-factor-lab-requirements.md` | 本文档 | ✅ |
| `docs/13-factor-lab-frontend.md` | 前端页面需求（待写） | ❌ |

## 六、价值

### 做完了能做什么

- 对任何基于日线的量价因子，定义公式 → IC/分层评估全流程 < 30s（3000 只）或 < 5s（沪深 300）
- 因子评估结论有数据支撑（IC 序列、分层收益、衰减曲线）
- 后续 P1 回测直接复用：评估通过的因子 → SE_MultiFactor → System → TradeManager
- 缓存机制让因子切换时的 forward returns 秒出

### 做完了不能做什么

- 不能做因子组合（需 P2，可直接用 hikyuu MF_ICIRWeight）
- 不能做策略回测（需 P1）
- 不能做实盘交易
- 没有前端界面（CLI only，前端见 doc/13）
