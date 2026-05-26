#!/usr/bin/env python3
"""hikyuu RAG 索引构建脚本 — 文档 → 切片 → Embedding → ChromaDB"""

import hashlib
import time
import sys
from pathlib import Path

import chromadb

from .config import CHROMA_PATH, DOC_SOURCES, CHUNK_SIZE, CHUNK_OVERLAP
from .chunker import read_document, chunk_markdown, chunk_notebook
from .embedding import embed_texts

COLLECTION_NAME = "hikyuu_docs"


def file_hash(path: str) -> str:
    """文件内容 MD5，用于增量更新判断"""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def collect_files(sources: list[dict]) -> list[dict]:
    """收集所有待处理文件"""
    files = []
    for src in sources:
        path = src["path"]
        if src.get("is_dir"):
            if not path.is_dir():
                print(f"  ⚠️ 目录不存在: {path}")
                continue
            for f in sorted(path.rglob("*")):
                if f.suffix.lower() in (".md", ".ipynb", ".rst"):
                    files.append({**src, "path": f})
        else:
            if path.exists():
                files.append(src)
            else:
                print(f"  ⚠️ 文件不存在: {path}")
    return files


def build(force: bool = False) -> dict:
    """
    构建索引

    Args:
        force: True 强制重建（清空已有数据）

    Returns:
        {"doc_count": N, "chunk_count": N, "files": [...]}
    """
    print("=" * 60)
    print("  hikyuu RAG 索引构建")
    print("=" * 60)

    # 1. 收集文件
    files = collect_files(DOC_SOURCES)
    print(f"\n  找到 {len(files)} 个文档文件\n")

    # 2. 初始化 ChromaDB
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 3. 逐文件切片 + Embedding + 入库
    all_docs = []
    all_ids = []
    all_metadatas = []
    file_stats = []

    for i, finfo in enumerate(files, 1):
        fpath = finfo["path"]
        rel = fpath.relative_to(finfo.get("base", fpath.parent.parent))
        name = fpath.name

        print(f"  [{i}/{len(files)}] {name} ...", end=" ")

        try:
            text = read_document(fpath)
        except Exception as e:
            print(f"❌ 读取失败: {e}")
            continue

        # 切片
        if fpath.suffix.lower() == ".ipynb":
            chunks = chunk_notebook(text, CHUNK_SIZE, CHUNK_OVERLAP)
        else:
            chunks = chunk_markdown(text, CHUNK_SIZE, CHUNK_OVERLAP)

        if not chunks:
            print("⚠️ 无有效内容")
            continue

        # 生成 ID
        base_id = hashlib.md5(str(fpath).encode()).hexdigest()[:12]
        ids = [f"{base_id}_{j}" for j in range(len(chunks))]

        # 元数据
        metadatas = [
            {
                "source": finfo["source_name"],
                "category": finfo["category"],
                "file_path": str(fpath),
                "file_name": name,
                "chunk_index": j,
                "chunk_total": len(chunks),
                "char_count": len(c),
            }
            for j, c in enumerate(chunks)
        ]

        all_docs.extend(chunks)
        all_ids.extend(ids)
        all_metadatas.extend(metadatas)
        file_stats.append({
            "file": str(fpath),
            "chunks": len(chunks),
            "status": "ok",
        })

        print(f"✅ {len(chunks)} chunks")

    # 4. 批量 Embedding
    if not all_docs:
        print("\n❌ 没有可入库的文档")
        return {"doc_count": 0, "chunk_count": 0, "files": []}

    print(f"\n  总计 {len(all_docs)} 个 chunks，开始 Embedding...")
    all_embeddings = embed_texts(all_docs)

    # 5. 批量写入 ChromaDB
    print(f"  写入 ChromaDB...")
    batch_size = 100
    for i in range(0, len(all_docs), batch_size):
        collection.add(
            ids=all_ids[i : i + batch_size],
            documents=all_docs[i : i + batch_size],
            embeddings=all_embeddings[i : i + batch_size],
            metadatas=all_metadatas[i : i + batch_size],
        )

    result = {
        "doc_count": len(file_stats),
        "chunk_count": len(all_docs),
        "files": file_stats,
    }

    print(f"\n  ✅ 完成！{result['doc_count']} 个文档，{result['chunk_count']} 个 chunks\n")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="hikyuu RAG 索引构建")
    parser.add_argument("--force", action="store_true", help="强制重建索引")
    args = parser.parse_args()

    result = build(force=args.force)
