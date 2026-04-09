"""
AI-002 骨架 / AI-006 实现: DeepSeek/OpenAI LLM 调用封装
参考: docs/plan/README.md § AI-006, docs/调研/03-LLM接入与回复生成.md

功能：
- generate_reply(): 生成回复，含 Prompt Caching 和费用追踪
- summarize_article(): 文章摘要生成（缓存）
- 指数退避重试
- 累计 token 费用，超预算时抛出 BudgetExceededError
"""

from __future__ import annotations


class LLMClient:
    """LLM 调用封装（OpenAI 兼容接口）"""

    def __init__(self) -> None:
        raise NotImplementedError("AI-006: 待实现")
