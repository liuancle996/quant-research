# RAG 本地知识库 — 原理、方案与技术选型

> 日期: 2026-05-26
> 目的: 为 hikyuu 等量化框架搭建本地开发知识库，实现「不重复造轮子、不零散查文档」

## 一、RAG 核心原理

### 1.1 什么是 RAG

RAG (Retrieval-Augmented Generation) = **检索 + 生成**。不依赖模型记忆所有知识，而是「用时检索相关文档片段，注入到 prompt 中，让模型基于检索到的上下文生成答案」。

### 1.2 两阶段流程

```
离线阶段（索引构建）:
  原始文档 → 文本切片 → Embedding 向量化 → 存入向量数据库

在线阶段（查询检索）:
  用户问题 → Embedding 向量化 → 向量相似度检索 → Top-K 结果注入 Prompt → LLM 生成
```

### 1.3 关键组件

| 组件 | 作用 | 决策点 |
|------|------|--------|
| 文档解析 | MD/RST/IPYNB → 纯文本 | 格式多样性 |
| 文本切片 | 长文档 → 语义完整的小块 | chunk_size, overlap |
| Embedding 模型 | 文本 → 向量 | 本地 vs API，中文支持 |
| 向量数据库 | 存储 + 相似度检索 | 性能、运维成本 |
| 检索策略 | 召回相关文档 | Top-K, MMR, 重排序 |
| Prompt 模板 | 拼接检索结果 → LLM 输入 | 结构化程度 |

---

## 二、向量数据库对比

### 2.1 候选方案总览

| 方案 | 语言 | 部署 | 存储 | 性能 | 社区 |
|------|------|------|------|------|------|
| **ChromaDB** | Python | 嵌入式 | SQLite | 中等 | ⭐⭐⭐⭐⭐ (最火) |
| **LanceDB** | Rust+Python | 嵌入式 | Lance(列存) | 高 | ⭐⭐⭐ |
| **FAISS** | C++ | 嵌入式 | 内存/磁盘 | ⭐最高 | ⭐⭐⭐⭐ |
| **Qdrant** | Rust | 独立进程 | RocksDB | 高 | ⭐⭐⭐⭐ |
| **Milvus** | Go/C++ | 独立/集群 | 多种 | 最高 | ⭐⭐⭐⭐ |
| **sqlite-vec** | C | SQLite扩展 | SQLite | 中等 | ⭐⭐ |

### 2.2 详细分析

#### ChromaDB — 最「开箱即用」

```
pip install chromadb
```

- **优点**: API 极简（3 行代码建库），内置多种 embedding，自动持久化
- **缺点**: 数据量大后性能下降，依赖较多（onnxruntime, hnswlib）
- **适合**: 文档量 < 10 万，快速原型
- **嵌入支持**: OpenAI / Cohere / HuggingFace / 自定义

#### LanceDB — 最「轻量无依赖」

```
pip install lancedb
```

- **优点**: 纯 Rust 内核，零外部依赖，列式存储压缩率高，支持多模态
- **缺点**: 社区较小，文档不如 ChromaDB 完善
- **适合**: 追求极致轻量，数据量中等
- **嵌入支持**: 需自行生成向量后写入

#### FAISS — 最「快」

```
pip install faiss-cpu  # 或 faiss-gpu
```

- **优点**: Meta 出品，检索速度业界最快，支持 GPU 加速
- **缺点**: 不管理元数据，需要自己封装，无内置持久化
- **适合**: 百万级以上向量检索，对速度要求极高
- **嵌入支持**: 纯向量存储，需外部生成

#### Qdrant — 最「工程化」

```
docker run -p 6333:6333 qdrant/qdrant
```

- **优点**: Rust 编写，性能优异，自带 Web UI，支持过滤/分组
- **缺点**: 需独立进程（内存 50MB+），对本地开发稍重
- **适合**: 生产级部署

---

## 三、Embedding 模型对比

### 3.1 方案总览

| 方案 | 类型 | 中文支持 | 维度 | 部署 |
|------|------|---------|------|------|
| **DeepSeek Embedding** | API | ✅ | 1024/4096 | 无需（已有 key） |
| **bge-small-zh** | 本地模型 | ✅ 专为中文优化 | 512 | 需下载 (~100MB) |
| **all-MiniLM-L6-v2** | 本地模型 | 一般 | 384 | 需下载 (~80MB) |
| **text2vec-large-chinese** | 本地模型 | ✅ 中文 | 1024 | 需下载 (~400MB) |

### 3.2 实际选型

**ChromaDB + fastembed + bge-small-zh-v1.5**（已落地于 M1）

```python
pip install chromadb fastembed
```

ChromaDB 嵌入式部署（SQLite 存储），fastembed 提供本地 ONNX 推理（零 GPU 依赖）。

模型 `BAAI/bge-small-zh-v1.5`：中文优化，512 维向量，模型文件 ~100MB，首次下载后完全离线。

---

## 四、文本切片策略

### 4.1 切片粒度

| 策略 | chunk_size | overlap | 适用 |
|------|-----------|---------|------|
| 固定字符 | 500-1000 | 100-200 | 通用 |
| 按段落 | 自然段落 | — | 结构化文档 |
| 按标题 | 按 # / ## 分割 | — | Markdown 文档 |
| 语义切片 | 模型判定 | — | 非结构化文本 |

### 4.2 推荐：Markdown 感知切片

hikyuu 文档以 Markdown 为主，应按 `#` 标题层级切片：

```
## 因子管理
### Factor 类
#### Factor 构造函数
```

每段保持 500-1000 字符，overlap 100-200，确保代码块不被截断。

---

## 五、实际技术架构

```
文档源                    嵌入层               向量库          检索接口
┌──────────┐         ┌────────────┐     ┌──────────┐    ┌──────────┐
│ *.md      │         │ fastembed  │     │ ChromaDB │    │ Python   │
│ *.ipynb   │ ──切片→ │ bge-small  │ ──→ │ (SQLite) │ ←─ │ CLI/Skill│
│ *.py 示例 │         │ -zh (ONNX) │     │ 本地持久  │    │ API      │
└──────────┘         └────────────┘     └──────────┘    └──────────┘
```

- ChromaDB 嵌入式 + SQLite 存储，零运维
- fastembed 本地 ONNX 推理，无需 API key，完全离线
- bge-small-zh-v1.5 中文优化，512 维

**依赖**:
```bash
pip install chromadb fastembed   # 已安装
```

---

## 六、检索策略

### 基础策略

1. **Top-K 检索**: 返回相似度最高的 K 个片段（K=5~10）
2. **MMR (最大边际相关)**: 平衡相关性和多样性，避免冗余

### Prompt 模板

```
你是一个 hikyuu 量化框架专家。根据以下参考文档回答问题。

参考文档:
{retrieved_chunks}

问题: {user_question}

请基于参考文档回答，如果文档中没有相关信息，请明确说明。
```

---

## 七、与 Hermes 集成

### 作为 Skill

创建 `~/.hermes/skills/hikyuu-knowledge/` skill，触发词如 `hikyuu`、`因子计算`、`回测策略` 等：

```markdown
---
name: hikyuu-knowledge
description: "检索 hikyuu 文档知识库，回答 API 用法和最佳实践"
triggers: [hikyuu, 因子, 回测, 策略, 指标, 交易系统, 选股]
---

## 使用

当用户询问 hikyuu 相关的 API 用法、策略编写、因子计算等问题时，
调用 RAG 检索接口获取相关文档片段，基于检索结果回答。
```

### 作为独立 CLI

```bash
python -m rag_hikyuu query "动量因子怎么写"
# → 返回相关文档片段 + 代码示例
```

---

## 八、实施计划

### Phase 1: 文档准备
- [ ] 导出 hikyuu Jupyter Notebooks → Markdown
- [ ] 收集 docs/source/*.md 文档
- [ ] 清洗格式，统一编码

### Phase 2: 索引构建
- [ ] 实现 Markdown 感知切片器
- [ ] 调用 DeepSeek Embedding API
- [ ] 存入 ChromaDB

### Phase 3: 检索接口
- [ ] Python API: `search(query, top_k=5)`
- [ ] Hermes Skill: 对话中自然触发
- [ ] CLI: 命令行快速查询

### Phase 4: 持续完善
- [ ] 加入 akshare 数据源文档
- [ ] 加入量化策略最佳实践
- [ ] 加入常见错误和修复方案

---

## 九、参考资料

- ChromaDB: https://docs.trychroma.com/
- LanceDB: https://lancedb.github.io/lancedb/
- DeepSeek API: https://platform.deepseek.com/api-docs/
- bge-small-zh: https://huggingface.co/BAAI/bge-small-zh-v1.5
- LangChain RAG: https://python.langchain.com/docs/tutorials/rag/
