"""tests/test_discussion_bot.py — discussion_bot 脚本单元测试."""

from __future__ import annotations

import pytest
from typing import Optional

# 确保 scripts/ 目录在路径中
import importlib.util
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.discussion_bot import (
    BOT_MARKER,
    BOT_FOOTER,
    build_reply,
    has_bot_replied,
    _fetch_more_comments,
    get_viewer_login,
)


# ── build_reply ───────────────────────────────────────────────────────────────


def test_build_reply_contains_answer():
    reply = build_reply("CSM 是一种状态机框架。")
    assert "CSM 是一种状态机框架。" in reply


def test_build_reply_contains_footer():
    reply = build_reply("some answer")
    assert BOT_FOOTER in reply


def test_build_reply_contains_bot_marker():
    reply = build_reply("some answer")
    assert BOT_MARKER in reply


def test_build_reply_order():
    """回复顺序应为：答案 → 页脚 → 标记。"""
    reply = build_reply("answer text")
    ans_pos = reply.index("answer text")
    footer_pos = reply.index(BOT_FOOTER)
    marker_pos = reply.index(BOT_MARKER)
    assert ans_pos < footer_pos <= marker_pos


def test_build_reply_strips_trailing_whitespace_from_answer():
    """答案末尾空白应被去除，不影响页脚格式。"""
    reply = build_reply("answer   \n\n")
    # 回复不应以多余空行开始页脚
    assert "answer" in reply
    assert BOT_FOOTER in reply


def test_build_reply_multiline_answer():
    """多行答案应完整保留。"""
    answer = "第一行\n第二行\n第三行"
    reply = build_reply(answer)
    assert "第一行" in reply
    assert "第三行" in reply


# ── has_bot_replied ───────────────────────────────────────────────────────────


def _make_discussion(comments: list[str], author: str = "user") -> dict:
    """构造最小化的 discussion dict。"""
    return {
        "comments": {
            "nodes": [{"id": f"c{i}", "body": body, "author": {"login": author}} for i, body in enumerate(comments)]
        }
    }


def test_has_bot_replied_false_when_no_comments():
    disc = _make_discussion([])
    assert has_bot_replied(disc) is False


def test_has_bot_replied_false_when_no_marker():
    disc = _make_discussion(["普通回复，没有标记。", "另一条回复。"])
    assert has_bot_replied(disc) is False


def test_has_bot_replied_true_when_marker_present_no_login_check():
    """不提供 bot_login 时，仅凭 marker 判断（向下兼容），不验证作者。"""
    disc = _make_discussion(["普通回复", f"Bot 回复内容 {BOT_MARKER}"])
    # bot_login=None：只要有 marker 就返回 True
    assert has_bot_replied(disc) is True
    assert has_bot_replied(disc, bot_login=None) is True


def test_has_bot_replied_author_check_wrong_author():
    """提供 bot_login 但评论作者不匹配时应返回 False（防伪造 marker 攻击）。"""
    disc = _make_discussion(["普通回复", f"Bot 回复内容 {BOT_MARKER}"])
    # disc 中 author 是 "user"，而 bot_login 是 "real-bot" → 不匹配
    assert has_bot_replied(disc, bot_login="real-bot") is False


def test_has_bot_replied_true_when_marker_present():
    disc = _make_discussion(["普通回复", f"Bot 回复内容 {BOT_MARKER}"])
    assert has_bot_replied(disc) is True


def test_has_bot_replied_author_check_match():
    """提供 bot_login，且作者匹配时返回 True。"""
    disc = {
        "comments": {
            "nodes": [
                {"id": "c0", "body": "普通回复", "author": {"login": "user"}},
                {"id": "c1", "body": f"Bot 回复 {BOT_MARKER}", "author": {"login": "my-bot"}},
            ]
        }
    }
    assert has_bot_replied(disc, bot_login="my-bot") is True


def test_has_bot_replied_author_check_no_match():
    """提供 bot_login，marker 存在但作者不匹配（用户伪造 marker）时返回 False。"""
    disc = {
        "comments": {
            "nodes": [
                {"id": "c0", "body": f"恶意评论 {BOT_MARKER}", "author": {"login": "attacker"}},
            ]
        }
    }
    assert has_bot_replied(disc, bot_login="my-bot") is False


def test_has_bot_replied_handles_none_body():
    """comment body 为 None 时不应抛出异常。"""
    disc = {
        "comments": {
            "nodes": [
                {"id": "c0", "body": None, "author": {"login": "user"}},
                {"id": "c1", "body": f"正常回复 {BOT_MARKER}", "author": {"login": "bot"}},
            ]
        }
    }
    assert has_bot_replied(disc) is True
    assert has_bot_replied(disc, bot_login="bot") is True
    assert has_bot_replied(disc, bot_login="other") is False


def test_has_bot_replied_handles_empty_body():
    disc = _make_discussion(["", "   "])
    assert has_bot_replied(disc) is False


def test_has_bot_replied_marker_in_first_comment():
    disc = _make_discussion([f"第一条即是 Bot 回复 {BOT_MARKER}", "第二条普通回复"])
    assert has_bot_replied(disc) is True


def test_has_bot_replied_author_is_none():
    """author 字段为 None（匿名评论）时不应崩溃。"""
    disc = {
        "comments": {
            "nodes": [
                {"id": "c0", "body": f"匿名回复 {BOT_MARKER}", "author": None},
            ]
        }
    }
    assert has_bot_replied(disc) is True
    assert has_bot_replied(disc, bot_login="my-bot") is False


# ── get_viewer_login ──────────────────────────────────────────────────────────


class _MockGraphQL:
    """最小化 mock GitHubGraphQL，直接返回预设 data。"""

    def __init__(self, return_data: dict, raise_error_message: Optional[str] = None):
        self._return_data = return_data
        self._raise_error_message = raise_error_message

    def query(self, gql: str, variables: Optional[dict] = None) -> dict:
        if self._raise_error_message:
            raise RuntimeError(self._raise_error_message)
        return self._return_data


def test_get_viewer_login_returns_login():
    client = _MockGraphQL({"viewer": {"login": "test-bot"}})
    assert get_viewer_login(client) == "test-bot"


def test_get_viewer_login_returns_none_on_error():
    client = _MockGraphQL({}, raise_error_message="Unauthorized")
    assert get_viewer_login(client) is None


def test_get_viewer_login_returns_none_when_missing():
    client = _MockGraphQL({"viewer": {}})
    assert get_viewer_login(client) is None


# ── _fetch_more_comments ──────────────────────────────────────────────────────


def test_fetch_more_comments_returns_empty_on_missing_node():
    """node 字段缺失时应返回空 comments 结构，而非抛出。"""
    client = _MockGraphQL({"node": {}})
    result = _fetch_more_comments(client, "D_xxx", "cursor123")
    assert result["nodes"] == []
    assert result["pageInfo"]["hasNextPage"] is False
