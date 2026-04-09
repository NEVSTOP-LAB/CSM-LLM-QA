"""
AI-002 骨架 / AI-003 实现: 知乎 API 封装
参考: docs/plan/README.md § AI-003, docs/调研/01-知乎数据获取.md

功能：
- ZhihuClient(cookie) 封装知乎 API v4 读写操作
- get_comments(object_id, object_type, since_id) 获取评论（分页、限流）
- post_comment(object_id, object_type, content, parent_id) 发布评论
- Cookie 失效时抛出 ZhihuAuthError
"""

from __future__ import annotations


class ZhihuClient:
    """知乎 API v4 客户端封装"""

    def __init__(self, cookie: str) -> None:
        raise NotImplementedError("AI-003: 待实现")
