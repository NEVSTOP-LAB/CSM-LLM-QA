"""
AI-002 骨架 / AI-007 实现: 对话线程管理
参考: docs/plan/README.md § AI-007, docs/调研/05-回复归档与存储.md

功能：
- get_or_create_thread(): 创建或获取对话线程文件
- append_turn(): 追加一轮对话（机器人/真人）
- build_context_messages(): 构建 OpenAI messages 格式的上下文
"""

from __future__ import annotations


class ThreadManager:
    """对话线程文件管理器"""

    def __init__(self, archive_dir: str) -> None:
        raise NotImplementedError("AI-007: 待实现")
