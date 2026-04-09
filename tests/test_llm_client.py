"""
AI-006: LLMClient 单元测试
参考: docs/plan/README.md § AI-006 测试要求

测试覆盖：
- System Prompt 固定前缀（缓存友好）
- history_messages 正确拼接
- 重试逻辑（前2次失败第3次成功）
- 超预算时 BudgetExceededError
- summarize_article 缓存（第二次不触发 API）
"""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from scripts.llm_client import LLMClient, BudgetExceededError, SYSTEM_PROMPT_PREFIX


# ─── Mock 辅助 ──────────────────────────────────────────────────

def make_mock_response(
    content: str = "这是一条回复",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cache_hit_tokens: int = 0,
):
    """构造 mock OpenAI ChatCompletion 响应"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens
    mock_usage.prompt_cache_hit_tokens = cache_hit_tokens
    mock_resp.usage = mock_usage

    return mock_resp


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI 客户端"""
    with patch("scripts.llm_client.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_response()
        yield mock_client


@pytest.fixture
def llm_client(mock_openai_client) -> LLMClient:
    """创建测试用 LLMClient"""
    return LLMClient(
        api_key="test-key",
        base_url="https://api.test.com",
        model="deepseek-chat",
        max_tokens=250,
        temperature=0.7,
        budget_usd_per_day=0.50,
    )


# ─── System Prompt 测试 ──────────────────────────────────────────

class TestSystemPrompt:
    """测试 System Prompt 结构"""

    def test_system_prompt_prefix_fixed(self, llm_client, mock_openai_client) -> None:
        """System Prompt 应以固定前缀开始（缓存友好）"""
        llm_client.generate_reply(
            comment="测试评论",
            context_chunks=["Wiki 内容"],
            article_summary="文章摘要",
        )

        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_msg = messages[0]

        assert system_msg["role"] == "system"
        assert system_msg["content"].startswith(SYSTEM_PROMPT_PREFIX)

    def test_wiki_context_in_system(self, llm_client, mock_openai_client) -> None:
        """Wiki 片段应包含在 System Prompt 中"""
        llm_client.generate_reply(
            comment="测试",
            context_chunks=["Wiki 片段 A", "Wiki 片段 B"],
            article_summary="摘要",
        )

        messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
        system_content = messages[0]["content"]
        assert "Wiki 片段 A" in system_content
        assert "Wiki 片段 B" in system_content

    def test_article_summary_in_system(self, llm_client, mock_openai_client) -> None:
        """文章摘要应包含在 System Prompt 中"""
        llm_client.generate_reply(
            comment="测试",
            context_chunks=[],
            article_summary="CSM 方法论概述",
        )

        messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
        assert "CSM 方法论概述" in messages[0]["content"]


# ─── History Messages 测试 ──────────────────────────────────────

class TestHistoryMessages:
    """测试历史消息拼接"""

    def test_history_messages_appended(self, llm_client, mock_openai_client) -> None:
        """历史消息应正确拼接到 messages 列表中"""
        history = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回复"},
        ]

        llm_client.generate_reply(
            comment="新追问",
            context_chunks=["Wiki"],
            article_summary="摘要",
            history_messages=history,
        )

        messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
        # 结构应为: system + history[0] + history[1] + user(当前评论)
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "之前的问题"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "之前的回复"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "新追问"

    def test_no_history_two_messages(self, llm_client, mock_openai_client) -> None:
        """无历史时 messages 只有 system + user"""
        llm_client.generate_reply(
            comment="单条评论",
            context_chunks=[],
            article_summary="摘要",
        )

        messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


# ─── 重试逻辑测试 ──────────────────────────────────────────────

class TestRetryLogic:
    """测试指数退避重试"""

    @patch("scripts.llm_client.time.sleep")
    def test_retry_on_rate_limit(self, mock_sleep, llm_client, mock_openai_client) -> None:
        """RateLimitError 时重试，第3次成功"""
        from openai import RateLimitError

        mock_openai_client.chat.completions.create.side_effect = [
            RateLimitError("rate limit", response=MagicMock(status_code=429), body=None),
            RateLimitError("rate limit", response=MagicMock(status_code=429), body=None),
            make_mock_response("成功的回复"),
        ]

        reply, tokens = llm_client.generate_reply(
            comment="测试",
            context_chunks=[],
            article_summary="摘要",
        )

        assert reply == "成功的回复"
        assert mock_openai_client.chat.completions.create.call_count == 3

    @patch("scripts.llm_client.time.sleep")
    def test_retry_exhausted_raises(self, mock_sleep, llm_client, mock_openai_client) -> None:
        """所有重试耗尽后应抛出 RuntimeError"""
        from openai import RateLimitError

        mock_openai_client.chat.completions.create.side_effect = RateLimitError(
            "rate limit", response=MagicMock(status_code=429), body=None
        )

        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            llm_client.generate_reply(
                comment="测试",
                context_chunks=[],
                article_summary="摘要",
            )


# ─── 预算控制测试 ──────────────────────────────────────────────

class TestBudgetControl:
    """测试费用预算控制"""

    def test_budget_exceeded_raises(self, llm_client, mock_openai_client) -> None:
        """超过每日预算时应抛出 BudgetExceededError"""
        # 手动设置费用超限
        llm_client._daily_cost_usd = 0.60  # > 0.50 预算

        with pytest.raises(BudgetExceededError, match="预算"):
            llm_client.generate_reply(
                comment="测试",
                context_chunks=[],
                article_summary="摘要",
            )

    def test_cost_accumulates(self, llm_client, mock_openai_client) -> None:
        """多次调用应累计费用"""
        mock_openai_client.chat.completions.create.return_value = make_mock_response(
            prompt_tokens=1000, completion_tokens=200
        )

        initial_cost = llm_client.daily_cost
        llm_client.generate_reply("评论1", [], "摘要")
        cost_after_1 = llm_client.daily_cost

        llm_client.generate_reply("评论2", [], "摘要")
        cost_after_2 = llm_client.daily_cost

        assert cost_after_1 > initial_cost
        assert cost_after_2 > cost_after_1

    def test_reset_daily_cost(self, llm_client, mock_openai_client) -> None:
        """reset_daily_cost 应将费用归零"""
        llm_client._daily_cost_usd = 0.10
        llm_client.reset_daily_cost()
        assert llm_client.daily_cost == 0.0


# ─── summarize_article 测试 ──────────────────────────────────────

class TestSummarizeArticle:
    """测试文章摘要"""

    def test_summarize_returns_text(self, llm_client, mock_openai_client) -> None:
        """应返回摘要文本"""
        mock_openai_client.chat.completions.create.return_value = make_mock_response(
            content="这是文章摘要"
        )

        summary = llm_client.summarize_article("标题", "正文内容...")
        assert summary == "这是文章摘要"

    def test_summarize_cached(self, llm_client, mock_openai_client) -> None:
        """第二次调用同一文章应命中缓存，不触发 API"""
        mock_openai_client.chat.completions.create.return_value = make_mock_response(
            content="缓存的摘要"
        )

        # 第一次调用
        summary1 = llm_client.summarize_article("标题A", "正文A")
        call_count_1 = mock_openai_client.chat.completions.create.call_count

        # 第二次调用（相同参数）
        summary2 = llm_client.summarize_article("标题A", "正文A")
        call_count_2 = mock_openai_client.chat.completions.create.call_count

        assert summary1 == summary2
        assert call_count_2 == call_count_1  # 第二次不触发 API

    def test_summarize_different_articles_not_cached(self, llm_client, mock_openai_client) -> None:
        """不同文章不应共享缓存"""
        mock_openai_client.chat.completions.create.return_value = make_mock_response("摘要")

        llm_client.summarize_article("标题A", "正文A")
        llm_client.summarize_article("标题B", "正文B")

        assert mock_openai_client.chat.completions.create.call_count == 2


# ─── 返回值测试 ──────────────────────────────────────────────────

class TestReturnValues:
    """测试返回值格式"""

    def test_generate_reply_returns_tuple(self, llm_client, mock_openai_client) -> None:
        """generate_reply 应返回 (reply_text, total_tokens) 元组"""
        result = llm_client.generate_reply("评论", [], "摘要")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)

    def test_stats_property(self, llm_client) -> None:
        """stats 属性应返回使用统计字典"""
        stats = llm_client.stats
        assert "total_prompt_tokens" in stats
        assert "total_completion_tokens" in stats
        assert "total_cache_hit_tokens" in stats
        assert "daily_cost_usd" in stats
