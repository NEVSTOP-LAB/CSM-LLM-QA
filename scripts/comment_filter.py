"""
AI-002 骨架 / AI-008 实现: 评论前置过滤器
参考: docs/plan/README.md § AI-008

功能：
- should_skip(): 判断评论是否应跳过（广告、重复、超长等）
- truncate_comment(): 截断超长评论
"""

from __future__ import annotations


def should_skip(comment: object, settings: dict) -> tuple[bool, str]:
    """判断评论是否需要跳过，返回 (是否跳过, 原因)"""
    raise NotImplementedError("AI-008: 待实现")
