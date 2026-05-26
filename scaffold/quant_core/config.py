"""配置管理 — 环境变量 + 默认值"""

import os
from dataclasses import dataclass, field


@dataclass
class QuantConfig:
    data_dir: str = field(
        default_factory=lambda: os.environ.get(
            "QUANT_DATA_DIR", os.path.expanduser("~/.quant-data")
        )
    )
    db_url: str = field(
        default_factory=lambda: os.environ.get("QUANT_DB_URL", "sqlite:///~/.quant-data/quant.db")
    )


config = QuantConfig()
