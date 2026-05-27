# 因子实验室 — 需求对齐文档

> 日期: 2026-05-27
> 版本: v0.2 草案（含调研）
> 状态: 待确认

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

关键点：
- **预处理是必须的**：原始因子值受极端值、行业分布、市值规模影响，不做标准化/中性化的话 IC 分析没有意义
- **IC 要看时间序列**：不是看某一期的 IC，而是看滚动 IC 序列的均值、标准差、IR（IC_mean / IC_std）
- **分层收益看单调性**：Q5 - Q1 的 spread 是否显著，各组收益是否单调递增/递减
- **衰减看稳定性**：因子预测能力随持仓周期的衰减速度

### 1.2 hikyuu 已有的能力（实测验证）

hikyuu 2.7.9 内置了完整的机构级因子处理管线，**不需要从零搭建**：

| 环节 | hikyuu 能力 | 实测结果 |
|------|------------|----------|
| 因子定义 | `MA(CLOSE(), 20).name = 'MA20'` — 任何 Indicator 都可以作为因子 | ✓ |
| 批量计算 | `MF_EqualWeight([indicators], stocks, query, ref_stk)` | ✓ 3000只股票 335 天，MF 创建 0.0s |
| 标准化 | `mf.set_normalize(NORM_Zscore())` — Z-score 标准化 | ✓ 内置 |
| 行业中性化 | `mf.add_special_normalize("factor", NORM_Zscore(), category="行业板块")` | ✓ 内置 |
| 市值中性化 | `mf.add_special_normalize("factor", ..., style_inds=[LOG(CLOSE()*LIUTONGPAN())])` | ✓ 内置 |
| 横截面评分 | `mf.get_scores(date) → DataFrame(market_code, name, score)` | ✓ 2959/3000 有效 |
| IC/IR 加权 | `SE_MultiFactor(factor_set, mode="MF_ICIRWeight", ic_n=5, ic_rolling_n=120)` | ✓ 内置 |
| 选股过滤 | `SCFilter_Group | SCFilter_Price | SCFilter_AmountLimit | SCFilter_TopN` | ✓ 内置 |

### 1.3 hikyuu 缺失的（需要我们自己补）

| 缺失环节 | 说明 |
|----------|------|
| **IC 分析报告** | hikyuu 的 SE_MultiFactor 内部用了 IC，但不暴露 IC 序列/统计值给用户 |
| **IC 衰减曲线** | 不同 forward period 下 IC 的变化 |
| **分层收益分析** | 按因子分位分组，看各组未来收益（hikyuu 的 SCFilter_Group 能分组但不统计收益） |
| **因子分布可视化** | 因子值分布直方图、Q-Q 图等 |
| **评估报告 (tearsheet)** | 类似 alphalens 的一页式因子评估汇总 |

### 1.4 方案对比

| | 原方案 (v0.1) | 修正方案 (v0.2) |
|---|---|---|
| 因子计算 | 自己写 python 循环逐只计算 | 使用 hikyuu MF 系统批量计算 |
| 预处理 | 没有（原始值直接分析） | 使用 hikyuu NORM_Zscore + 行业/市值中性化 |
| 评估 | 自己写 IC / 分层 | 从 MF.get_all_scores() 提取评分 → pandas 做 IC/分层分析 |
| 代码量 | ~300 行（含因子计算引擎） | ~200 行（MF 封装 + 评估层） |
| 可靠性 | 自己保证数据对齐、日期处理 | hikyuu C++ 引擎保证，减少出错面 |

## 二、定位与边界

### 2.1 一句话定位

**基于 hikyuu MF 系统的因子评估层** — 利用 hikyuu 的因子计算和预处理能力，补齐 IC 分析、分层收益、衰减分析等评估环节，让因子研究形成闭环。

### 2.2 能做

- 定义因子 → hikyuu MF 批量计算 + 标准化/中性化 → 提取评分 → IC/分层/衰减分析
- 单因子评估报告：IC 统计 + IC 序列图 + IC 衰减曲线 + 分层收益 + 因子分布
- 支持 hikyuu 630 个内置指标的任意组合作为因子公式
- 行业中性化 / 市值中性化 一键开关

### 2.3 不能做（明确边界）

- 不是策略回测系统 — 不做信号生成、不下单
- 不是多因子组合框架 — 本版只做单因子评估（hikyuu 已有 MF_ICIRWeight，后续直接对接）
- 不做分钟线级别因子
- 不做基本面因子（依赖财报数据，hikyuu 日线数据不包含）

## 三、技术方案（修正版）

### 3.1 核心架构

```
hikyuu MF 系统（C++ 引擎）
  ├── 因子定义: Indicator → Factor formula
  ├── 批量计算: MF_EqualWeight(stocks, query, ref_stk)
  ├── 预处理: NORM_Zscore + 行业中性化 + 市值中性化
  └── 评分提取: mf.get_all_scores() → ScoreRecordList
           │
           ▼
    factor_lab/evaluation.py（Python 评估层）
  ├── extract_scores(): ScoreRecordList → pd.DataFrame(date × stock)
  ├── ic_analysis(): 时间序列 IC(mean/std/IR) + IC 衰减
  ├── quantile_returns(): 分层收益 + 单调性检验
  └── report(): 评估报告（文本 + 可选图表）
```

### 3.2 关键设计决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 因子计算 | 使用 hikyuu MF 系统 | 已有 C++ 实现，3000 只股票 335 天批量计算 < 1s |
| 预处理 | 使用 hikyuu NORM_Zscore + 中性化 | 机构级实现，不需要自己写 |
| 评估层 | pandas + scipy | IC/分层是纯统计计算，pandas 最适合 |
| 不自己写计算引擎 | 基于 hikyuu MF，只做评估 | 减少代码量，减少出错面，不重复造轮子 |

### 3.3 模块结构

```
factor_lab/
├── __init__.py
├── hikyuu_adapter.py      ← hikyuu 导入 + 环境初始化
├── mf_builder.py          ← MF 构建器：定义因子 + 创建 MF + 设置标准化/中性化
├── extraction.py          ← 从 MF 提取评分为 pandas DataFrame
├── evaluation.py          ← IC 分析 / 分层收益 / 衰减分析
├── factors/
│   ├── __init__.py
│   └── momentum.py        ← 动量因子示例
└── run.py                 ← CLI 入口
```

### 3.4 核心 API 设计

```python
# mf_builder.py
def build_mf(
    indicators: list,       # hikyuu Indicator 列表
    stocks: list,           # 股票列表
    start_date, end_date,   # 日期范围
    normalize: str = None,  # None | 'zscore'
    industry_neutral: bool = False,
    market_cap_neutral: bool = False,
) -> MF:
    """构建并配置 hikyuu MF 评分板"""

# extraction.py
def extract_scores(mf: MF) -> pd.DataFrame:
    """从 MF 提取所有日期的因子评分 → DataFrame(date × stock)"""

def extract_forward_returns(mf: MF, forward_days: int) -> pd.DataFrame:
    """提取 future returns 用于 IC 和分层计算"""

# evaluation.py
def ic_analysis(scores: pd.DataFrame, forward_returns: pd.DataFrame) -> dict:
    """IC 分析 → {ic_mean, ic_std, ic_ir, ic_series, ...}"""

def ic_decay(scores: pd.DataFrame, forward_returns: dict) -> pd.DataFrame:
    """IC 衰减 → DataFrame(days=[1,5,10,20,60], ic=[...])"""

def quantile_returns(scores: pd.DataFrame, forward_returns: pd.DataFrame, n_groups=5) -> pd.DataFrame:
    """分层收益 → DataFrame(group=[Q1..Q5], mean_ret=[...], ...)"""
```

## 四、验证方法

### 4.1 准确性验证

| 验证方法 | 具体做法 |
|----------|---------|
| 已知因子对照 | 动量因子 ROC(20)：业界公认 A 股动量效应较弱（甚至反转），如果 IC 显著为正反而可疑 |
| 小样本手工核算 | 取 5 只股票 × 5 天，手工用 Excel 算 IC，与代码输出对比 |
| 指数基准比对 | 分层收益应与沪深 300 指数同期收益比较，Top 组不应大幅偏离指数 |
| 数据完整性检查 | 评分覆盖 > 90% 股票（实测 2959/3000 = 98.6%） |

### 4.2 合理性验证

| 检查项 | 预期 |
|--------|------|
| IC 均值范围 | 单个量价因子 IC 通常在 -0.05 ~ 0.05 |
| 分层单调性 | Q1→Q5 不应出现明显锯齿（说明因子噪声大） |
| IC 衰减方向 | IC 应随 forward period 增加而衰减 |
| 中性化前后对比 | 行业中性化后 IC 应降低（说明原因子有行业暴露） |
| 极端值占比 | 评分中位数附近的组应有最多股票（Z-score 标准化的特征） |

## 五、MVP 验证目标

用**动量因子（ROC 20 日）**跑通全流程：

1. hikyuu MF 创建 + Z-score 标准化，3000 只股票，1 年回看期
2. 输出 IC 序列（每日滚动），IC 均值/标准差/IR
3. 输出 IC 衰减曲线（forward 1/5/10/20/60 天）
4. 输出 5 分组分层收益柱状图
5. 输出 Top/Bottom 20 股票列表
6. 对比标准化前后的差异

## 六、交付物

| 文件 | 说明 | 验收标准 |
|------|------|----------|
| `factor_lab/__init__.py` | 包初始化 | 正常 import |
| `factor_lab/hikyuu_adapter.py` | hikyuu 环境初始化 + 导入 | LD_PRELOAD + unset proxy |
| `factor_lab/mf_builder.py` | MF 构建器 | `build_mf()` 返回可用 MF 对象 |
| `factor_lab/extraction.py` | 评分提取 | `extract_scores()` 返回有效 DataFrame（~2959 × 335） |
| `factor_lab/evaluation.py` | IC/分层/衰减 | IC 计算与手工核算一致 |
| `factor_lab/factors/momentum.py` | 动量因子定义 | `create_momentum_factor(n=20)` |
| `factor_lab/run.py` | CLI 入口 | `python -m factor_lab.run` 输出完整报告 |
| `docs/12-factor-lab-requirements.md` | 本文档 | 确认后更新状态为「已确认」 |

## 七、价值

### 做完了能做什么

- 对任何基于日线的量价因子，定义公式 → 标准化 → IC/分层 全流程 < 5 分钟
- 因子评估结论有数据支撑（IC 序列、分层收益、衰减曲线），不是凭感觉
- 后续 P1 回测直接复用：评估通过的因子 → SE_MultiFactor → System → TradeManager
- 因子预处理（标准化/中性化）使用了机构级实现，不需要手动验证

### 做完了不能做什么

- 不能做因子组合（需 P2，可直接用 hikyuu MF_ICIRWeight）
- 不能做策略回测（需 P1）
- 不能做实盘交易
