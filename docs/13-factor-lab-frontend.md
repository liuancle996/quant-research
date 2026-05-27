# 因子实验室 — Streamlit 前端页面需求

> 日期: 2026-05-27
> 版本: v0.2 草案（布局对齐现有筛选器模式）
> 状态: 待确认

## 一、背景

`factor_lab/` CLI 引擎已交付（doc/12），支持命令行因子评估。现在需要 Web 前端。

## 二、布局约束（对齐现有筛选器）

当前筛选器使用 `st.navigation(position="sidebar")`，侧边栏已被导航菜单占据。所有页面的筛选/控制区统一放在**主内容区顶部**（`st.expander` 折叠面板），结果区在下方。

因子实验室页面遵循同一模式。

## 三、页面布局

```
┌─────────────────────────────────────────────────────────┐
│  📈 因子实验室                                           │
├─────────────────────────────────────────────────────────┤
│  ▼ 运行参数                          [展开/折叠]          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  因子类型    参数 n    前向天数    股票池            │  │
│  │  [动量 ▼]   [20   ]   [20    ]   ○ 沪深300        │  │
│  │  标准化     中性化              [🚀 运行分析]       │  │
│  │  ☐ Z-score  ☐ 行业 ☐ 市值                         │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────┬──────┬──────┬──────┐                          │
│  │ IC均值 │ IC IR │ IC>0 │ 覆盖率 │  指标卡片              │
│  │ 0.004 │ 0.25  │ 59%  │ 70只  │                          │
│  └──────┴──────┴──────┴──────┘                          │
│                                                         │
│  IC 序列折线图                                           │
│  ┌────────────────────────────────────────────┐        │
│  │ ▁▃▅▂▁▄▆▃▁▂▅▇▃▁...                          │        │
│  └────────────────────────────────────────────┘        │
│                                                         │
│  IC 衰减  |  分层收益                                   │
│  (柱状图)  |  (柱状图：Q1-Q5分组收益)                     │
│                                                         │
│  Top 20 / Bottom 20 表格                                 │
└─────────────────────────────────────────────────────────┘
```

### 3.1 控制区（`st.expander` 内，默认展开）

参照 `pages/01_筛选器.py` 的控件风格，使用 `st.columns` 多列布局：

**第 1 行（4 列）：**
| 列 | 控件 | 类型 | 默认值 |
|----|------|------|--------|
| 1 | 因子类型 | `selectbox` | momentum |
| 2 | 参数 n | `number_input` | 20 |
| 3 | 前向天数 | `number_input` | 20 |
| 4 | 股票池 | `radio` | 沪深300 |

**第 2 行（5 列）：**
| 列 | 控件 | 类型 | 默认值 |
|----|------|------|--------|
| 1 | Z-score 标准化 | `checkbox` | ☐ |
| 2 | 行业中性化 | `checkbox` | ☐ |
| 3 | 市值中性化 | `checkbox` | ☐ |
| 4 | 显示 IC 衰减 | `checkbox` | ☐ |
| 5 | [🚀 运行分析] | `button` | — |

### 3.2 结果区

| 区域 | 内容 | 实现 |
|------|------|------|
| 指标卡片 | IC 均值、IC IR、IC>0 占比、覆盖率 | `st.metric` × 4 |
| IC 序列 | 每日 IC 折线图 | Plotly `go.Scatter` |
| 因子分布 | 直方图 + 密度曲线 | Plotly `go.Histogram` |
| IC 衰减 + 分层收益 | 并排两列 | 左：IC 衰减柱状图，右：分层收益柱状图 |
| 排名表格 | Top 20 + Bottom 20（含股票名称） | `st.dataframe` × 2 并排 |

## 四、页面注册

在 `screener/app.py` 中新增：

```python
"因子研究": [
    st.Page("pages/06_因子实验室.py", title="因子实验室", icon="🧪"),
],
```

## 五、技术要点

### 5.1 与 CLI 共享代码

直接 import `factor_lab` 模块：
```python
from factor_lab.mf_builder import build_mf, get_a_share_universe
from factor_lab.extraction import extract_scores, get_or_compute_forward_returns
from factor_lab.evaluation import ic_analysis, quantile_returns, ic_decay
from factor_lab.factors import momentum, volatility, price_position, volume_ratio
from factor_lab.hikyuu_adapter import sm
```

### 5.2 沪深 300 获取

```python
hs300 = sm.get_block("指数板块", "沪深300")
stocks = list(hs300)  # 277 只
```

### 5.3 性能

| 股票池 | 耗时 | 用户体验 |
|--------|------|----------|
| 沪深 300 | < 5s | `st.spinner` 等待，即时响应 |
| 全量 A 股 | 24-60s | `st.spinner` + 进度提示 |

### 5.4 session_state

分析结果（IC、分层、衰减）存 `st.session_state`，避免控件切换丢失。只有点击"运行分析"才重新计算。

## 六、交付物

| 文件 | 说明 |
|------|------|
| `screener/pages/06_因子实验室.py` | Streamlit 页面 |
| `screener/app.py` | 新增页面注册 + 导航分组 |
| `docs/13-factor-lab-frontend.md` | 本文档 |

## 七、价值

### 做完了能做什么

- 浏览器上选因子/调参数 → 5s 出 IC/分层/衰减可视化
- 不切终端，不记 CLI 命令
- 4 个因子一键切换对比

### 做完了不能做什么

- 不能做策略回测（P1）
- 不能做多因子组合（P2）
- 不能导出报告
