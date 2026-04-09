"""
AI-011: Wiki 同步辅助脚本
参考: docs/plan/README.md § AI-011

功能：
- fetch_wiki(): 拉取 CSM Wiki 到本地目录
- 当前版本：本地目录已存在，无需网络拉取
- 未来可扩展为从 GitHub Wiki 或其他来源同步
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def fetch_wiki(wiki_dir: str) -> bool:
    """
    确保 Wiki 目录存在

    Args:
        wiki_dir: Wiki 本地目录路径

    Returns:
        True 如果目录存在或创建成功
    """
    path = Path(wiki_dir)
    if path.exists():
        logger.info("Wiki 目录已存在: %s", wiki_dir)
        return True

    path.mkdir(parents=True, exist_ok=True)
    logger.info("创建 Wiki 目录: %s", wiki_dir)
    return True
