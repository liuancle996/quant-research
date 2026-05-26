"""hikyuu RAG 检索接口"""

from pathlib import Path

import chromadb

from .config import CHROMA_PATH, DEFAULT_TOP_K
from .embedding import embed_single

COLLECTION_NAME = "hikyuu_docs"


def search(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    检索 hikyuu 知识库

    Args:
        query: 查询文本
        top_k: 返回结果数

    Returns:
        [{"content": "...", "metadata": {...}, "score": 0.95}, ...]
    """
    if not CHROMA_PATH.exists():
        raise FileNotFoundError(f"索引不存在: {CHROMA_PATH}，请先运行 build_index.py")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        raise FileNotFoundError("集合不存在，请先运行 build_index.py")

    # Query embedding
    query_vec = embed_single(query)

    # 检索
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    # 格式化结果
    output = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "content": doc,
                "metadata": meta,
                "score": 1.0 - dist,  # cosine distance → similarity
            })

    return output
