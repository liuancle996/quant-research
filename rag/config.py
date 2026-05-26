"""配置管理"""

import os
from pathlib import Path

# === 路径 ===
RAG_HOME = Path(os.environ.get("RAG_HOME", os.path.expanduser("~/.rag-hikyuu")))
CHROMA_PATH = RAG_HOME / "chroma"
HIKYUU_REPO = Path(os.environ.get("HIKYUU_REPO", os.path.expanduser("~/project/quant-research/repos/hikyuu")))

PROJECT_ROOT = Path(os.environ.get("QUANT_PROJECT_ROOT", os.path.expanduser("~/project/quant-research")))

# === 文档源 ===
DOC_SOURCES = [
    # hikyuu 框架文档
    {
        "path": HIKYUU_REPO / "readme.md",
        "category": "金融量化/框架文档",
        "source_name": "hikyuu README",
    },
    {
        "path": HIKYUU_REPO / "docs" / "source" / "factor.md",
        "category": "金融量化/框架文档",
        "source_name": "hikyuu 因子管理",
    },
    {
        "path": HIKYUU_REPO / "docs" / "source" / "trade_portfolio",
        "category": "金融量化/框架文档",
        "source_name": "hikyuu 投资组合",
        "is_dir": True,
    },
    {
        "path": HIKYUU_REPO / "docs" / "source" / "release.md",
        "category": "金融量化/框架文档",
        "source_name": "hikyuu 更新日志",
    },
    {
        "path": HIKYUU_REPO / "hikyuu" / "examples" / "notebook",
        "category": "金融量化/示例代码",
        "source_name": "hikyuu Jupyter 示例",
        "is_dir": True,
    },
    # 项目知识文档
    {
        "path": PROJECT_ROOT / "docs" / "05-hikyuu-research.md",
        "category": "项目知识/技术调研",
        "source_name": "hikyuu 调研报告",
    },
    {
        "path": PROJECT_ROOT / "docs" / "06-rag-knowledge-base.md",
        "category": "项目知识/技术调研",
        "source_name": "RAG 技术选型",
    },
    {
        "path": PROJECT_ROOT / "docs" / "07-rag-requirements-alignment.md",
        "category": "项目知识/需求文档",
        "source_name": "RAG 需求对齐",
    },
    {
        "path": PROJECT_ROOT / "docs" / "08-screener-requirements.md",
        "category": "项目知识/需求文档",
        "source_name": "筛选器需求",
    },
    {
        "path": PROJECT_ROOT / "docs" / "09-hikyuu-integration-guide.md",
        "category": "项目知识/开发规范",
        "source_name": "hikyuu 集成规范",
    },
]

# === Embedding ===
# 本地模型（优先）
LOCAL_EMBEDDING_MODEL = os.environ.get(
    "RAG_EMBEDDING_MODEL",
    "BAAI/bge-small-zh-v1.5",  # 中文优化, 512维, ~100MB
)
# API 模式（备选，本地模型不可用时自动切换）
EMBEDDING_API_URL = os.environ.get("EMBEDDING_API_URL", "https://api.deepseek.com/v1/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "deepseek-chat")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_BATCH_SIZE = 32

# === 切片参数 ===
CHUNK_SIZE = 800      # 每片最大字符数
CHUNK_OVERLAP = 150   # 片间重叠字符数

# === 检索参数 ===
DEFAULT_TOP_K = 5
