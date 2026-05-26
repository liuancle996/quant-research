"""文档解析 + 切片 — 支持 Markdown, Jupyter Notebook"""

import json
from pathlib import Path


def parse_ipynb(path: Path) -> str:
    """Jupyter Notebook → 纯文本（提取 markdown 和 code cells）"""
    with open(path, encoding="utf-8") as f:
        nb = json.load(f)

    parts = []
    for cell in nb.get("cells", []):
        source = "".join(cell.get("source", []))
        if cell["cell_type"] == "markdown":
            parts.append(source)
        elif cell["cell_type"] == "code":
            parts.append(f"```python\n{source}\n```")
    return "\n\n".join(parts)


def read_document(path: Path) -> str:
    """读取文档，支持 .md / .ipynb / .rst"""
    suffix = path.suffix.lower()
    if suffix == ".ipynb":
        return parse_ipynb(path)
    elif suffix in (".md", ".rst", ".txt"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def chunk_markdown(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Markdown 感知切片：
    - 优先按 ## 标题边界切
    - 超长段落再按固定大小切
    - 保留 overlap 防止语义断裂
    """
    # 按 ## 标题分段
    sections = text.split("\n## ")
    # 恢复被 split 移除的 '## '
    for i in range(1, len(sections)):
        sections[i] = "## " + sections[i]

    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # 超长 section，按固定大小切
            start = 0
            while start < len(section):
                end = start + chunk_size
                chunk = section[start:end]
                chunks.append(chunk)
                if end >= len(section):
                    break
                start = end - overlap

    return chunks


def chunk_notebook(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Notebook 文本切片：优先按 markdown cell 边界"""
    # 按连续的 markdown/code 块分
    # 简化处理：先用空行分段，再合并短段
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para) if current else para
        else:
            if current:
                chunks.append(current)
            # 如果单个段超长，硬切
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i : i + chunk_size])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks
