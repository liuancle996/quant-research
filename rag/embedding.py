"""Embedding 接口 — 本地 fastembed 模型（零 GPU 依赖）"""

import time
from typing import Optional

import numpy as np

from .config import EMBEDDING_BATCH_SIZE, LOCAL_EMBEDDING_MODEL

_model: Optional["TextEmbedding"] = None


def _get_model():
    """懒加载 fastembed 模型"""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        print(f"  加载本地 Embedding 模型: {LOCAL_EMBEDDING_MODEL} ...")
        _model = TextEmbedding(LOCAL_EMBEDDING_MODEL)
        print(f"  ✅ 模型就绪")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本 → 向量（自动分批）"""
    if not texts:
        return []

    model = _get_model()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        embeddings = list(model.embed(batch))
        all_embeddings.extend([e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings])

    return all_embeddings


def embed_single(text: str) -> list[float]:
    """单文本 → 向量"""
    return embed_texts([text])[0]
