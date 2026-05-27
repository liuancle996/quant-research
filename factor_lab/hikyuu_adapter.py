"""hikyuu 导入适配层 — 统一的环境初始化和导入入口

所有 factor_lab 模块通过本文件导入 hikyuu，确保：
- LD_PRELOAD 和 proxy 环境变量正确设置
- load_hikyuu() 只执行一次（Python 模块缓存保证）
"""

import os
import sys

# 环境初始化（必须在 import hikyuu 之前）
for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(var, None)

if 'LD_PRELOAD' not in os.environ:
    os.environ['LD_PRELOAD'] = '/usr/lib/x86_64-linux-gnu/libstdc++.so.6'

# 导入 hikyuu — 此行触发 load_hikyuu()
from hikyuu.interactive import *  # noqa: F401, E402, F403

# 额外导入 MF 系统需要的类型
from hikyuu.cpp.core313 import Query as _Query  # noqa: E402

# 导出 Query.RecoverType 便于使用
NO_RECOVER = _Query.RecoverType.NO_RECOVER
