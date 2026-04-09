"""
AI-002 骨架 / AI-005 实现: ChromaDB + BGE embedding RAG 检索
参考: docs/plan/README.md § AI-005, docs/调研/04-CSM-Wiki-RAG知识库.md

功能：
- RAGRetriever: Wiki 增量 embedding + 检索
- sync_wiki(): MD5 比对增量更新
- retrieve(): reply_index 优先 + wiki 补充
- index_human_reply(): 高权重写入
"""

from __future__ import annotations


class RAGRetriever:
    """CSM Wiki RAG 检索器"""

    def __init__(self, wiki_dir: str, vector_store_dir: str,
                 reply_index_dir: str, use_online_embedding: bool = False) -> None:
        raise NotImplementedError("AI-005: 待实现")
