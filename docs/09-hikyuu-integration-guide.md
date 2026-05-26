# hikyuu 项目集成规范

> 日期: 2026-05-26
> 版本: v1.0
> 状态: 已确认

## 一、核心踩坑：`import hikyuu` vs `from hikyuu.interactive import *`

### 问题

```python
# ❌ 错误用法 — StockManager 加载不到数据
import hikyuu
sm = hikyuu.StockManager.instance()
len(sm)          # 0！数据全是空的
sm['sz000001']   # Segfault 或空对象

# ✅ 正确用法 — StockManager 完整初始化
from hikyuu.interactive import *
len(sm)          # 8310
sm['sz000001']   # 平安银行，数据正常
```

### 根因

`hikyuu.interactive` 额外调用了 `load_hikyuu()`，该方法负责：
- 读取 `~/.hikyuu/hikyuu.ini` 配置
- 连接 SQLite 数据库（stock.db）
- 连接 HDF5 K线文件
- 预加载日线数据到内存缓存
- 加载板块/权息等辅助数据

```python
# hikyuu/interactive.py 源码
from hikyuu import *
load_hikyuu()    # ← 关键！没有这一步，数据就是空的
```

### 解决：单例适配层

项目中有且仅有一个文件 `from hikyuu.interactive import *`，其他模块从适配层引入。

```python
# screener/hikyuu_adapter.py   ← 唯一导入点
from hikyuu.interactive import *

# screener/engine.py           ← 从适配层取
from .hikyuu_adapter import sm, Query, constant
```

Python 模块缓存保证：无论多少个文件 import，`sm` 只初始化一次。

## 二、项目架构

```
~/project/quant-research/
├── screener/                      ← 股票筛选器（新模块）
│   ├── __init__.py
│   ├── hikyuu_adapter.py          ← 单例：from hikyuu.interactive import *
│   ├── engine.py                  ← 筛选核心逻辑
│   ├── app.py                     ← Streamlit Web 前端（8082端口）
│   └── run.sh                     ← 一键启动
│
├── rag/                           ← 知识库（已完成 M1）
│   ├── __init__.py
│   ├── build_index.py
│   ├── search.py
│   ├── embedding.py
│   ├── chunker.py
│   ├── config.py
│   └── __main__.py
│
├── scaffold/                      ← 已有基础组件
│   ├── quant_core/                ← 配置管理
│   └── quant_data/                ← 数据层（备用）
│
├── docs/                          ← 文档
│   ├── 05-hikyuu-research.md
│   ├── 07-rag-requirements-alignment.md
│   ├── 08-screener-requirements.md
│   └── 09-hikyuu-integration-guide.md  ← 本文档
│
└── repos/                         ← 上游源码
    └── hikyuu/
```

## 三、数据更新

### 当前状态

| 项目 | 状态 |
|------|------|
| 数据截止日 | 2026-05-13 |
| A股数量 | 3196 只 |
| ST 股票 | 196 只 |
| 数据加载 | 0.37 秒（预热后） |

### 更新命令

```bash
cd /path/to/hikyuu
python hikyuu/data/pytdx_to_h5.py
```

建议配置 cron 每天 18:00 自动执行。更新后 Streamlit 刷新页面即可看到最新数据。

### 注意事项

- pytdx 依赖通达信行情服务器，需要在交易时段后（15:00 之后）下载
- HDF5 文件使用 zlib level 9 压缩，增量更新只下载新数据
- 更新期间不影响 Streamlit 读取（HDF5 支持并发读）

## 四、hikyuu 核心 API 速查

### StockManager

```python
from screener.hikyuu_adapter import sm

sm['sz000001']              # 按代码获取股票
sm.get_stock_list()         # 迭代所有证券（8310 只）
len(sm)                     # 证券总数
```

### Stock 属性

```python
s = sm['sz000001']
s.name           # '平安银行'
s.market         # 'SZ' | 'SH' | 'BJ'
s.market_code    # 'SZ000001'
s.type           # 1=A股, 2=指数, 3=ETF...
s.valid          # True=有效, False=退市
```

### K线

```python
k = s.get_kdata(Query(-20))     # 最近 20 条日线
k = s.get_kdata(Query(100))     # 最近 100 条
k = s.get_kdata(Query_by_date(start, end, KQuery.DAY))  # 日期范围

r = k[0]
r.open            # 开盘价
r.high            # 最高价
r.low             # 最低价
r.close           # 收盘价
r.volume          # 成交量（股）
r.amount          # 成交额（元）
r.datetime        # 日期
len(k)            # K线条数
```

### 常量

```python
from screener.hikyuu_adapter import constant

constant.STOCKTYPE_A       # 1 = A股
constant.STOCKTYPE_INDEX   # 2 = 指数
```

## 五、筛选器设计（详见 `08-screener-requirements.md`）

### 筛选条件

| 条件 | hikyuu 实现 |
|------|------------|
| 交易所 | `s.market in ['SH', 'SZ']` |
| A股类型 | `s.type == constant.STOCKTYPE_A` |
| 有效状态 | `s.valid == True` |
| 排除 ST | `'ST' not in s.name` |
| 时间区间涨幅 | `Query(-N)` → 首尾 close 对比 |
| 最小成交量 | `k[-1].volume > min_vol` |

### 前端

- 框架：Streamlit
- 端口：8082
- 布局：左侧筛选条件 + 右侧结果表格 + 图表

## 六、交付物 + 价值

### 交付物

| 文件 | 说明 |
|------|------|
| `screener/hikyuu_adapter.py` | hikyuu 单例适配层 |
| `screener/engine.py` | 筛选引擎 |
| `screener/app.py` | Streamlit 前端 |
| `screener/run.sh` | 启动脚本 |
| `docs/09-hikyuu-integration-guide.md` | 本文档 |

### 价值

| 能做的 | 不能做的 |
|--------|---------|
| ✅ 按涨跌幅/成交量/ST 筛选全A股 | ❌ 不能按流通市值筛选（无数据） |
| ✅ 浏览器 8082 直接操作 | ❌ 首次全市场筛选约 2-3 分钟 |
| ✅ 结果排序 + CSV 导出 | ❌ 实时行情（盘后数据） |
| ✅ hikyuu 正确用法模板，后续项目复用 | |

---

*方案已对齐，确认后进入代码编写。*
