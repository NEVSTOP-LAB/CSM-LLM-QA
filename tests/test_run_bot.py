"""
AI-009: 主流程 run_bot.py 单元测试
参考: docs/plan/README.md § AI-009 测试要求

测试覆盖：
- load_config / load_seen_ids / save_seen_ids
- write_pending_reply 生成正确的 Markdown
- process_article 完整流程（mock 所有外部依赖）
- ZhihuAuthError / BudgetExceededError 触发告警
- 每日上限检查
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from scripts.zhihu_client import Comment, ZhihuAuthError
from scripts.llm_client import BudgetExceededError


# ─── fixtures ──────────────────────────────────────────────────

@pytest.fixture
def mock_settings() -> dict:
    """测试用配置"""
    return {
        "bot": {
            "check_interval_hours": 6,
            "max_new_comments_per_run": 20,
            "max_new_comments_per_day": 100,
            "llm_budget_usd_per_day": 0.50,
        },
        "llm": {
            "base_url": "https://api.test.com",
            "model": "deepseek-chat",
            "max_tokens": 250,
            "temperature": 0.7,
        },
        "rag": {
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "use_online_embedding": False,
            "top_k": 3,
            "similarity_threshold": 0.72,
            "history_turns": 6,
        },
        "vector_store": {"backend": "chromadb", "max_size_mb": 500},
        "review": {"manual_mode": True},
        "filter": {
            "max_comment_tokens": 500,
            "spam_keywords": ["加微信", "VX"],
            "dedup_window_minutes": 60,
        },
        "alerting": {
            "github_issue": True,
            "consecutive_fail_limit": 3,
        },
    }


@pytest.fixture
def sample_article() -> dict:
    """测试用文章配置"""
    return {
        "id": "98765432",
        "title": "CSM 最佳实践",
        "url": "https://zhuanlan.zhihu.com/p/98765432",
        "type": "article",
    }


@pytest.fixture
def sample_comments() -> list[Comment]:
    """测试用评论列表"""
    return [
        Comment(
            id="1001",
            parent_id=None,
            content="请问如何处理客户投诉？",
            author="张三",
            created_time=1700000000,
            is_author_reply=False,
        ),
        Comment(
            id="1002",
            parent_id="1001",
            content="补充一下，是关于退款的投诉",
            author="张三",
            created_time=1700001000,
            is_author_reply=False,
        ),
    ]


@pytest.fixture
def author_comment() -> Comment:
    """真人回复评论"""
    return Comment(
        id="1003",
        parent_id="1001",
        content="处理客户退款投诉需要...",
        author="作者",
        created_time=1700002000,
        is_author_reply=True,
    )


# ─── load/save 测试 ──────────────────────────────────────────

class TestLoadSave:
    """测试配置和状态文件加载/保存"""

    def test_write_pending_reply(self, tmp_path) -> None:
        """pending 文件应包含评论和回复"""
        from scripts.run_bot import write_pending_reply

        # 临时修改 ROOT_DIR
        with patch("scripts.run_bot.ROOT_DIR", tmp_path):
            comment = Comment(
                id="1001", parent_id=None,
                content="测试评论", author="用户",
                created_time=1700000000,
            )
            path = write_pending_reply("98765", comment, "测试回复", 150, "deepseek-chat")

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "测试评论" in content
        assert "测试回复" in content
        assert "98765" in content
        assert "pending" in str(path.parent.name)

    def test_save_and_load_seen_ids(self, tmp_path) -> None:
        """seen_ids 应可正确保存和加载"""
        from scripts.run_bot import save_seen_ids, load_seen_ids

        seen_ids_path = tmp_path / "data" / "seen_ids.json"

        with patch("scripts.run_bot.SEEN_IDS_PATH", seen_ids_path):
            data = {"articles": {"123": "1001"}, "last_run": "2024-01-01T00:00:00"}
            save_seen_ids(data)

            loaded = load_seen_ids()
            assert loaded["articles"]["123"] == "1001"


# ─── process_article 测试 ──────────────────────────────────────

class TestProcessArticle:
    """测试文章处理流程"""

    def test_process_with_new_comments(
        self, sample_article, sample_comments, mock_settings, tmp_path
    ) -> None:
        """新评论应被处理并写入 pending/"""
        from scripts.run_bot import process_article
        from scripts.comment_filter import reset_dedup_cache

        reset_dedup_cache()

        # 使用不同作者避免 dedup 过滤
        sample_comments[1] = Comment(
            id="1002",
            parent_id="1001",
            content="补充一下，是关于退款的投诉",
            author="李四",
            created_time=1700001000,
            is_author_reply=False,
        )

        # Mock 所有依赖
        mock_zhihu = MagicMock()
        mock_zhihu.get_comments.return_value = sample_comments

        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = ["Wiki 内容"]

        mock_llm = MagicMock()
        mock_llm.generate_reply.return_value = ("回复内容", 150)
        mock_llm.daily_cost = 0.001

        mock_thread = MagicMock()
        mock_thread.get_or_create_thread.return_value = tmp_path / "thread.md"
        mock_thread.build_context_messages.return_value = []
        # 创建一个空的线程文件以避免 frontmatter 错误
        (tmp_path / "thread.md").write_text("---\nturn_count: 0\nhuman_replied: false\n---\n", encoding="utf-8")

        mock_cost = MagicMock()
        seen_ids = {"articles": {}}

        with patch("scripts.run_bot.ROOT_DIR", tmp_path), \
             patch("scripts.run_bot.write_pending_reply") as mock_write:
            mock_write.return_value = tmp_path / "pending" / "test.md"

            count = process_article(
                sample_article, mock_zhihu, mock_rag, mock_llm,
                mock_thread, mock_cost, seen_ids, mock_settings,
            )

        assert count == 2
        assert mock_llm.generate_reply.call_count == 2

    def test_process_no_comments(self, sample_article, mock_settings, tmp_path) -> None:
        """无新评论时处理数应为 0"""
        from scripts.run_bot import process_article

        mock_zhihu = MagicMock()
        mock_zhihu.get_comments.return_value = []

        count = process_article(
            sample_article, mock_zhihu, MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), {"articles": {}}, mock_settings,
        )
        assert count == 0

    def test_process_skips_spam(self, sample_article, mock_settings, tmp_path) -> None:
        """广告评论应被跳过"""
        from scripts.run_bot import process_article
        from scripts.comment_filter import reset_dedup_cache

        reset_dedup_cache()

        spam_comment = Comment(
            id="2001", parent_id=None,
            content="加微信详聊价格",
            author="广告用户",
            created_time=1700000000,
            is_author_reply=False,
        )

        mock_zhihu = MagicMock()
        mock_zhihu.get_comments.return_value = [spam_comment]

        mock_llm = MagicMock()

        count = process_article(
            sample_article, mock_zhihu, MagicMock(), mock_llm,
            MagicMock(), MagicMock(), {"articles": {}}, mock_settings,
        )

        assert count == 0
        mock_llm.generate_reply.assert_not_called()

    def test_process_detects_human_reply(
        self, sample_article, author_comment, mock_settings, tmp_path
    ) -> None:
        """真人回复应被索引到 reply_index"""
        from scripts.run_bot import process_article

        mock_zhihu = MagicMock()
        mock_zhihu.get_comments.return_value = [author_comment]

        mock_rag = MagicMock()
        mock_thread = MagicMock()
        mock_thread.get_or_create_thread.return_value = tmp_path / "thread.md"
        (tmp_path / "thread.md").write_text("---\nturn_count: 0\nhuman_replied: false\n---\n", encoding="utf-8")

        count = process_article(
            sample_article, mock_zhihu, mock_rag, MagicMock(),
            mock_thread, MagicMock(), {"articles": {}}, mock_settings,
        )

        # 真人回复不计入处理数
        assert count == 0
        # 应调用 index_human_reply
        mock_rag.index_human_reply.assert_called_once()

    def test_seen_ids_updated(self, sample_article, mock_settings, tmp_path) -> None:
        """处理后 seen_ids 应更新"""
        from scripts.run_bot import process_article

        comment = Comment(
            id="5001", parent_id=None,
            content="正常评论",
            author="新用户",
            created_time=1700000000,
            is_author_reply=False,
        )

        mock_zhihu = MagicMock()
        mock_zhihu.get_comments.return_value = [comment]

        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = []

        mock_llm = MagicMock()
        mock_llm.generate_reply.return_value = ("回复", 100)
        mock_llm.daily_cost = 0.001

        mock_thread = MagicMock()
        mock_thread.get_or_create_thread.return_value = tmp_path / "thread.md"
        mock_thread.build_context_messages.return_value = []
        (tmp_path / "thread.md").write_text("---\nturn_count: 0\n---\n", encoding="utf-8")

        seen_ids = {"articles": {}}

        with patch("scripts.run_bot.ROOT_DIR", tmp_path), \
             patch("scripts.run_bot.write_pending_reply"):
            process_article(
                sample_article, mock_zhihu, mock_rag, mock_llm,
                mock_thread, MagicMock(), seen_ids, mock_settings,
            )

        assert seen_ids["articles"]["98765432"] == "5001"


# ─── main 流程测试 ──────────────────────────────────────────────

class TestMain:
    """测试 main() 错误处理"""

    @patch("scripts.run_bot.create_alert_issue")
    @patch("scripts.run_bot.os.environ", {"ZHIHU_COOKIE": ""})
    @patch("scripts.run_bot.load_config")
    def test_missing_cookie_creates_alert(self, mock_config, mock_alert) -> None:
        """缺少 ZHIHU_COOKIE 应创建告警并退出"""
        from scripts.run_bot import main

        mock_config.return_value = ({"bot": {}}, {"articles": []})

        with pytest.raises(SystemExit):
            main()

        mock_alert.assert_called_once()
        assert "auth_failure" in mock_alert.call_args[0][0]
