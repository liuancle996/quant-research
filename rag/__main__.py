#!/usr/bin/env python3
"""hikyuu RAG CLI — 命令行检索工具

用法:
    python -m rag search "动量因子怎么定义"
    python -m rag build [--force]
    python -m rag stat
"""

import argparse
import sys
from pathlib import Path

# 确保能 import rag
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def cmd_search(args):
    from rag.search import search

    try:
        results = search(args.query, top_k=args.top_k)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    if not results:
        print("未找到相关结果。")
        return

    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        print(f"\n{'─' * 60}")
        print(f"  #{i}  [{meta.get('source', '?')}] {meta.get('file_name', '?')}")
        print(f"      相似度: {r['score']:.4f}  |  chunk {meta.get('chunk_index',0)+1}/{meta.get('chunk_total',0)}")
        print(f"  {'─' * 56}")

        # 截断显示
        content = r["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        print(content)


def cmd_build(args):
    from rag.build_index import build

    result = build(force=args.force)

    # 生成报告
    report_path = Path(__file__).resolve().parent / "INDEX_REPORT.md"
    from datetime import date

    lines = [
        f"# hikyuu RAG 索引报告",
        f"",
        f"> 构建时间: {date.today()}",
        f"> 文档数: {result['doc_count']}",
        f"> Chunk 数: {result['chunk_count']}",
        f"",
        f"## 文档明细",
        f"",
        f"| 文件 | Chunks | 状态 |",
        f"|------|--------|------|",
    ]
    for f in result["files"]:
        name = Path(f["file"]).name
        lines.append(f"| {name} | {f['chunks']} | {f['status']} |")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  报告已生成: {report_path}")


def cmd_stat(args):
    from rag.config import CHROMA_PATH
    import chromadb

    if not CHROMA_PATH.exists():
        print("索引尚未构建。运行: python -m rag build")
        return

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        collection = client.get_collection("hikyuu_docs")
        count = collection.count()
        print(f"  索引位置: {CHROMA_PATH}")
        print(f"  Chunk 总数: {count}")

        # 来源统计
        if count > 0:
            metas = collection.get(include=["metadatas"], limit=min(count, 10000))
            sources = {}
            for m in metas["metadatas"]:
                src = m.get("source", "unknown")
                sources[src] = sources.get(src, 0) + 1
            print(f"\n  来源分布:")
            for src, cnt in sorted(sources.items()):
                print(f"    {src}: {cnt} chunks")
    except Exception:
        print("集合不存在。运行: python -m rag build")


def main():
    parser = argparse.ArgumentParser(description="hikyuu RAG 知识库 CLI")
    sub = parser.add_subparsers(dest="command")

    # search
    p = sub.add_parser("search", help="检索知识库")
    p.add_argument("query", help="查询文本")
    p.add_argument("-k", "--top_k", type=int, default=5, help="返回结果数 (默认 5)")

    # build
    p = sub.add_parser("build", help="构建/重建索引")
    p.add_argument("--force", action="store_true", help="强制重建")

    # stat
    sub.add_parser("stat", help="查看索引状态")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "stat":
        cmd_stat(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
