"""
hikyuu 数据适配层
================
本项目唯一直接 from hikyuu.interactive import * 的文件。
其他模块从本模块导入 sm, Query, constant。

Python 模块缓存保证 load_hikyuu() 只执行一次。
"""

from hikyuu.interactive import *  # noqa: F401, F403 — 这是唯一入口

# 显式导出核心对象，方便 IDE 自动补全
sm = StockManager.instance()
Query = Query
constant = constant
