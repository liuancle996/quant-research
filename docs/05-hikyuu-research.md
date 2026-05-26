# hikyuu 调研报告

> 日期: 2026-05-26
> 版本: hikyuu 2.7.9
> 状态: 已确认

## 一、正确用法

```python
from hikyuu.interactive import *   # 必须！含 load_hikyuu()

sm['sz000001']           # 平安银行
s.get_kdata(Query(-20))  # 最近 20 条日线
```

**常见坑**：`import hikyuu` 不会调 `load_hikyuu()`，导致 StockManager 是空的（`len(sm)=0`）。详见 `09-hikyuu-integration-guide.md`。

## 二、数据资产

```
~/stock/         总计 4.8 GB
├── stock.db                  1.2 GB   SQLite (8311 只证券)
├── sh_day.h5 / sz_day.h5     ~400MB   沪深日线
├── sh_1min / sz_1min         ~2.7GB   沪深 1 分钟线
├── sh_5min / sz_5min         ~430MB   沪深 5 分钟线
└── bj_day / bj_1min / ...    ~150MB   北证
```

| 统计项 | 数值 |
|--------|------|
| 证券总数 | 8310 |
| A 股 (type=1, valid) | 3196 只 |
| 上证 A 股 | 1704 |
| 深证 A 股 | 1492 |
| ST 股票 | 196 只 |
| 数据最新日 | 2026-05-13 |
| 加载时间 | 0.37 秒 |

## 三、核心 API

```python
from hikyuu.interactive import *

# StockManager
sm['sz000001']                 # 按代码取股票
sm.get_stock_list()            # 迭代所有证券

# Stock
s.name                         # '平安银行'
s.market                       # 'SZ' | 'SH' | 'BJ'
s.market_code                  # 'SZ000001'
s.type == constant.STOCKTYPE_A # 是否 A 股
s.valid                        # 是否有效

# K线
k = s.get_kdata(Query(-20))    # 最近 20 条
r = k[0]
r.open, r.close, r.volume      # OHLCV
```

## 四、数据更新

```bash
# 每天 18:00 后执行增量更新
python hikyuu/data/pytdx_to_h5.py
```

使用 pytdx（通达信协议）从行情服务器下载增量数据。数据存储到 HDF5（zlib level 9 压缩）。

## 五、代理问题

服务器配置了 `HTTP_PROXY=http://localhost:8118`，但代理服务不可用。运行 Python 脚本时需：

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
```

## 六、GLIBCXX 兼容性问题

conda 环境的 libstdc++ 版本（GLIBCXX_3.4.26）低于 hikyuu 要求（3.4.31+）。启动任何使用 hikyuu 的脚本前需 preload 系统库：

```bash
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
```
