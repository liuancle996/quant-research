# A股筛选器 — 需求对齐文档

> 日期: 2026-05-26
> 版本: v1.0
> 状态: 已交付（MVP 引擎，已扩展至 P0/P1/P2）

## 一、背景

基于 hikyuu 已有的 4.8GB A 股全量数据（8311 只证券），搭建一个股票筛选器，
支持按涨跌幅、成交量、ST 等条件筛选，前端运行在 8082 端口。

## 二、数据来源

**hikyuu HDF5 + SQLite**（唯一数据源）

```
~/stock/
├── stock.db        SQLite   基础信息（代码/名称/类型/有效状态）
├── sh_day.h5       HDF5     上证日线（OHLCV）
├── sz_day.h5       HDF5     深证日线
└── bj_day.h5       HDF5     北证日线
```

hikyuu API 封装了底层存储，代码中统一通过 `StockManager` 访问。

## 三、筛选条件（已确认）

| 条件 | hikyuu 实现 | 说明 |
|------|------------|------|
| 交易所 | `s.market in ['SH', 'SZ']` | SH=上证, SZ=深证 |
| A股类型 | `s.type == constant.STOCKTYPE_A` | 排除指数/ETF/债券 |
| 有效状态 | `s.valid == True` | 排除退市 |
| 排除 ST | `'ST' not in s.name` | 名称含 ST 即排除 |
| 时间区间 | `Query(-N)` → 首尾 close | 自定义天数 |
| 涨跌幅 | `(end_p / start_p - 1) * 100` | 可设最小/最大 |
| 最小成交量 | `k[-1].volume > min_vol` | 过滤流动性差的 |

## 四、前端设计（8082 端口）

### 技术选型

**Streamlit** — 已安装，纯 Python，零前端代码，适合快速出 MVP。

### 页面布局

```
┌──────────────────────────────────────────────────┐
│  📊 A股筛选器                                      │
├───────────────┬──────────────────────────────────┤
│  筛选条件       │  结果表格                          │
│               │                                  │
│  交易所:       │ 代码   名称   最新价   涨跌幅   成交量  │
│  □ 上证 □ 深证 │ 000001 平安   12.50  +3.2%  150万  │
│  □ 创业板      │ 600519 茅台  1850   +1.8%   8万   │
│               │ ...                              │
│  时间区间:     │                                  │
│  [1月    ▼]   │                                  │
│               │──────────────────────────────────│
│  涨跌幅:       │  涨幅分布图                        │
│  [  -5  ] ~   │  ▁▃▅▇█▇▅▃▁                      │
│  [  20  ] %   │                                  │
│               │                                  │
│  最小成交量:   │  成交量分布图                       │
│  [50000] 手   │  ▁▂▃▅▇██▇▅▃▂▁                   │
│               │                                  │
│  ☑ 排除 ST    │                                  │
│  ☑ 排除退市   │                                  │
│               │                                  │
│  [🔍 开始筛选] │                                  │
│               │                                  │
│  状态: 共筛选  │                                  │
│  出 47 只股票  │                                  │
└───────────────┴──────────────────────────────────┘
```

### 页面要素

- 左侧：筛选条件面板
- 右侧上方：结果表格（可排序、可点击查看详情）
- 右侧下方：统计图表（涨幅分布、成交量分布）

## 五、交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 筛选引擎 | `screener/engine.py` | 基于 hikyuu 的筛选核心逻辑 |
| 数据适配层 | `screener/hikyuu_adapter.py` | 封装 hikyuu 数据读取（StockManager + KData） |
| Streamlit 前端 | `screener/app.py` | 8082 端口 Web 界面 |
| 启动脚本 | `screener/run.sh` | 一键启动 |
| 需求文档 | `docs/08-screener-requirements.md` | 本文档 |

## 六、价值

| 能做的 | 不能做的 |
|--------|---------|
| ✅ 按涨跌幅/成交量/ST 筛选全 A 股 | ❌ 还不能按市值筛选（缺数据） |
| ✅ 自定义时间区间 | ❌ 数据不是实时（盘后更新） |
| ✅ 浏览器直接访问 8082 | ❌ 首次加载较慢（需遍历全市场） |
| ✅ 结果可视化（分布图） | |
| ✅ 结果可导出 CSV | |

## 七、数据更新流程

```
每天 18:00 后:
  python -m hikyuu.data.pytdx_to_h5  # 增量更新日线
  → SH/SZ 日线 HDF5 更新至当日
  → 筛选器数据自动同步
```

当前数据截止：2026-05-13，需要更新。

## 八、已确认决策

| # | 议题 | 决策 |
|---|------|------|
| 1 | 数据源 | hikyuu（pytdx 下载），不用 akshare |
| 2 | ST 判定 | 名称包含 'ST' |
| 3 | 前端框架 | Streamlit |
| 4 | 端口 | 8082 |
| 5 | 数据更新 | 18:00 后手动跑 `pytdx_to_h5` |
| 6 | hikyuu 导入 | `from hikyuu.interactive import *`，单例适配层 |
| 7 | 性能 | 全市场约 2.5 分钟，后续可加缓存 |

## 九、技术设计

### 9.1 文件职责

```
screener/
├── hikyuu_adapter.py   ← 唯一入口: from hikyuu.interactive import *
│                          导出: sm, Query, constant
├── engine.py           ← 纯逻辑，无 UI 依赖
│    screen(**params) → pd.DataFrame
└── app.py              ← Streamlit UI
    调用 engine.screen() → st.dataframe() + st.pyplot()
```

### 9.2 engine.screen() 函数签名

参数列表（全部可选，有默认值）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| markets | list[str] | ["SH", "SZ"] | 交易所 |
| lookback_days | int | 20 | 回看交易日数 |
| min_pct | float 或 None | None | 最小涨幅(%)，None=不限 |
| max_pct | float 或 None | None | 最大涨幅(%)，None=不限 |
| min_volume | int 或 None | None | 最小日均成交量(股)，None=不限 |
| exclude_st | bool | True | 是否排除 ST |
| top_n | int | 50 | 返回前 N 只 |
| sort_by | str | "pct_change" | 排序字段：pct_change 或 volume |
| ascending | bool | False | True=升序，False=降序 |

返回值：pd.DataFrame（10 列，见 9.4）

### 9.3 数据流（3 步）

**步骤 1：获取候选池**  
遍历 `sm.get_stock_list()`，过滤条件：A股（type=A）、有效（valid=True）、交易所属于 markets。预估约 3000 只。

**步骤 2：逐只计算指标并过滤**  
对每只股票：
- 取最近 N 个交易日 K 线 `s.get_kdata(Query(-lookback_days))`
- K 线条数不足 2 → 跳过
- 计算涨幅 `(最后一天收盘 / 第一天收盘 - 1) × 100`
- 与 min_pct / max_pct 比较 → 不符合则跳过
- 排除 ST（如果开启）：名称含 'ST' → 跳过
- 计算日均成交量 `mean(volume)`，与 min_volume 比较 → 不符合则跳过
- 通过所有条件 → 加入结果列表

**步骤 3：排序并截取 Top-N**  
按 sort_by 排序（ascending 控制方向），取前 top_n 条，返回 DataFrame。

### 9.4 返回 DataFrame 格式

| 列名 | 类型 | 说明 |
|------|------|------|
| code | str | sz000001 |
| name | str | 平安银行 |
| market | str | SH / SZ |
| latest_price | float | 最新收盘价 |
| start_price | float | lookback 起始价 |
| end_price | float | lookback 结束价 |
| pct_change | float | 涨幅(%) |
| avg_volume | int | 日均成交量(股) |
| latest_volume | int | 最新成交量(股) |
| n_days | int | 有效交易日数 |

### 9.5 错误处理

| 情况 | 处理 |
|------|------|
| 某只股票无 K 线数据 | skip，不报错 |
| K 线条数不足 | skip（最少 2 条才能算涨幅） |
| 结果为空 | 返回空 DataFrame + 日志提示 |
| hikyuu 初始化失败 | 抛 RuntimeError，app 层捕获显示错误页 |

### 9.6 hikyuu_adapter 设计

`screener/hikyuu_adapter.py` 是项目中唯一直接 `from hikyuu.interactive import *` 的文件。其他模块从该适配层导入 `sm`, `Query`, `constant`。Python 模块缓存保证 `load_hikyuu()` 只执行一次。

### 9.7 页面结构

左侧面板：筛选条件（交易所多选、时间区间下拉、涨跌幅范围、最小成交量、ST开关）  
右侧主区域：结果表格（可排序）+ 统计分布图（涨幅直方图、成交量直方图）  
点击「开始筛选」按钮后触发筛选并展示结果。

---

*方案已对齐，确认后进入代码编写。*
