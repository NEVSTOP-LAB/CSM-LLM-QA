"""
AI-003: ZhihuClient 单元测试
参考: docs/plan/README.md § AI-003 测试要求

测试覆盖：
- 正常分页（article 和 question 各一组）、is_end=True 停止
- 429 重试逻辑
- 401 抛出 ZhihuAuthError
- Comment 字段映射
- post_comment 目标 URL 为 https://api.zhihu.com/v4/comments
- post_comment 请求头包含从 Cookie 提取的 x-xsrftoken
- Mock POST 成功：返回 True
- Mock POST 失败（401）：返回 False，不抛出异常
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from scripts.zhihu_client import ZhihuClient, Comment, ZhihuAuthError, ZhihuRateLimitError


# ─── 测试用常量 ──────────────────────────────────────────────────

TEST_COOKIE = "z_c0=test_z_c0_value; _xsrf=test_xsrf_token_123; d_c0=test_dc0"

# 模拟知乎 API 返回的评论数据
MOCK_COMMENT_1 = {
    "id": 1001,
    "content": "这篇文章写得很好",
    "author": {"name": "张三", "url_token": "zhangsan"},
    "created_time": 1700000000,
    "is_author": False,
    "reply_comment": None,
}

MOCK_COMMENT_2 = {
    "id": 1002,
    "content": "请问如何处理客户投诉？",
    "author": {"name": "李四", "url_token": "lisi"},
    "created_time": 1700001000,
    "is_author": False,
    "reply_comment": {"id": 1001, "content": "这篇文章写得很好"},
}

MOCK_AUTHOR_COMMENT = {
    "id": 1003,
    "content": "感谢提问，客户投诉处理需要...",
    "author": {"name": "作者", "url_token": "author"},
    "created_time": 1700002000,
    "is_author": True,
    "reply_comment": {"id": 1002, "content": "请问如何处理客户投诉？"},
}


# ─── 辅助函数 ──────────────────────────────────────────────────

def make_api_response(comments: list, is_end: bool = True) -> dict:
    """构造知乎 API 分页响应"""
    return {
        "data": comments,
        "paging": {
            "is_end": is_end,
            "next": "https://www.zhihu.com/api/v4/articles/123/comments?offset=20",
        },
    }


def make_mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    """构造 mock HTTP 响应"""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = str(json_data)
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=mock_resp
        )
    return mock_resp


# ─── 初始化测试 ──────────────────────────────────────────────────

class TestZhihuClientInit:
    """测试 ZhihuClient 初始化"""

    def test_init_success(self) -> None:
        """正常初始化：Cookie 包含 _xsrf"""
        client = ZhihuClient(TEST_COOKIE)
        assert client._xsrf == "test_xsrf_token_123"
        assert client.cookie == TEST_COOKIE

    def test_init_empty_cookie_raises(self) -> None:
        """空 Cookie 应抛出 ValueError"""
        with pytest.raises(ValueError, match="Cookie 不能为空"):
            ZhihuClient("")

    def test_init_missing_xsrf_raises(self) -> None:
        """Cookie 中缺少 _xsrf 应抛出 ValueError"""
        with pytest.raises(ValueError, match="未找到 _xsrf"):
            ZhihuClient("z_c0=some_value; other=123")


# ─── Comment 字段映射测试 ──────────────────────────────────────

class TestCommentParsing:
    """测试 Comment dataclass 字段映射"""

    def test_parse_normal_comment(self) -> None:
        """正常评论解析：所有字段映射正确"""
        comment = ZhihuClient._parse_comment(MOCK_COMMENT_1)
        assert comment.id == "1001"
        assert comment.parent_id is None
        assert comment.content == "这篇文章写得很好"
        assert comment.author == "张三"
        assert comment.created_time == 1700000000
        assert comment.is_author_reply is False

    def test_parse_reply_comment(self) -> None:
        """追问评论解析：parent_id 正确"""
        comment = ZhihuClient._parse_comment(MOCK_COMMENT_2)
        assert comment.id == "1002"
        assert comment.parent_id == "1001"
        assert comment.content == "请问如何处理客户投诉？"

    def test_parse_author_comment(self) -> None:
        """作者回复解析：is_author_reply=True"""
        comment = ZhihuClient._parse_comment(MOCK_AUTHOR_COMMENT)
        assert comment.id == "1003"
        assert comment.is_author_reply is True
        assert comment.parent_id == "1002"

    def test_comment_dataclass_fields(self) -> None:
        """Comment dataclass 应包含所有必要字段"""
        c = Comment(
            id="1", parent_id=None, content="test",
            author="user", created_time=0, is_author_reply=False
        )
        assert hasattr(c, "id")
        assert hasattr(c, "parent_id")
        assert hasattr(c, "content")
        assert hasattr(c, "author")
        assert hasattr(c, "created_time")
        assert hasattr(c, "is_author_reply")


# ─── get_comments 测试 ──────────────────────────────────────────

class TestGetComments:
    """测试 get_comments 方法"""

    @patch("scripts.zhihu_client.time.sleep")  # 跳过延迟
    def test_get_article_comments_single_page(self, mock_sleep) -> None:
        """article 类型：单页返回 is_end=True 时停止"""
        client = ZhihuClient(TEST_COOKIE)
        response_data = make_api_response([MOCK_COMMENT_1, MOCK_COMMENT_2], is_end=True)
        mock_resp = make_mock_response(200, response_data)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            comments = client.get_comments("12345", "article")

        assert len(comments) == 2
        assert comments[0].id == "1001"
        assert comments[1].id == "1002"
        # 验证请求 URL 包含 articles
        call_args = mock_req.call_args
        assert "articles/12345/comments" in call_args[0][1]

    @patch("scripts.zhihu_client.time.sleep")
    def test_get_question_comments(self, mock_sleep) -> None:
        """question 类型：使用 answers/{id}/comments 端点"""
        client = ZhihuClient(TEST_COOKIE)
        response_data = make_api_response([MOCK_COMMENT_1], is_end=True)
        mock_resp = make_mock_response(200, response_data)

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            comments = client.get_comments("67890", "question")

        assert len(comments) == 1
        call_args = mock_req.call_args
        assert "answers/67890/comments" in call_args[0][1]

    @patch("scripts.zhihu_client.time.sleep")
    def test_pagination_multi_page(self, mock_sleep) -> None:
        """多页分页：is_end=False 时继续请求下一页"""
        client = ZhihuClient(TEST_COOKIE)

        page1 = make_api_response([MOCK_COMMENT_1], is_end=False)
        page2 = make_api_response([MOCK_COMMENT_2], is_end=True)

        mock_resp1 = make_mock_response(200, page1)
        mock_resp2 = make_mock_response(200, page2)

        with patch.object(
            client.session, "request", side_effect=[mock_resp1, mock_resp2]
        ):
            comments = client.get_comments("12345", "article")

        assert len(comments) == 2
        assert comments[0].id == "1001"
        assert comments[1].id == "1002"

    @patch("scripts.zhihu_client.time.sleep")
    def test_since_id_filter(self, mock_sleep) -> None:
        """since_id 过滤：只返回 ID 大于 since_id 的评论"""
        client = ZhihuClient(TEST_COOKIE)
        response_data = make_api_response(
            [MOCK_COMMENT_1, MOCK_COMMENT_2, MOCK_AUTHOR_COMMENT],
            is_end=True,
        )
        mock_resp = make_mock_response(200, response_data)

        with patch.object(client.session, "request", return_value=mock_resp):
            comments = client.get_comments("12345", "article", since_id="1001")

        assert len(comments) == 2
        assert all(c.id > "1001" for c in comments)

    def test_invalid_object_type_raises(self) -> None:
        """不支持的 object_type 应抛出 ValueError"""
        client = ZhihuClient(TEST_COOKIE)
        with pytest.raises(ValueError, match="不支持的 object_type"):
            client.get_comments("12345", "invalid_type")


# ─── 错误处理测试 ──────────────────────────────────────────────

class TestErrorHandling:
    """测试 HTTP 错误处理"""

    @patch("scripts.zhihu_client.time.sleep")
    def test_401_raises_auth_error(self, mock_sleep) -> None:
        """HTTP 401 应抛出 ZhihuAuthError"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(401)

        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(ZhihuAuthError, match="401"):
                client.get_comments("12345", "article")

    @patch("scripts.zhihu_client.time.sleep")
    def test_403_raises_auth_error(self, mock_sleep) -> None:
        """HTTP 403 应抛出 ZhihuAuthError"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(403)

        with patch.object(client.session, "request", return_value=mock_resp):
            with pytest.raises(ZhihuAuthError, match="403"):
                client.get_comments("12345", "article")

    @patch("scripts.zhihu_client.time.sleep")
    def test_429_retry_then_success(self, mock_sleep) -> None:
        """HTTP 429：重试后成功"""
        client = ZhihuClient(TEST_COOKIE)

        mock_429 = make_mock_response(429)
        success_data = make_api_response([MOCK_COMMENT_1], is_end=True)
        mock_200 = make_mock_response(200, success_data)

        with patch.object(
            client.session, "request", side_effect=[mock_429, mock_200]
        ):
            comments = client.get_comments("12345", "article")

        assert len(comments) == 1

    @patch("scripts.zhihu_client.time.sleep")
    def test_429_all_retries_exhausted(self, mock_sleep) -> None:
        """HTTP 429：所有重试耗尽后抛出 ZhihuRateLimitError"""
        client = ZhihuClient(TEST_COOKIE)
        mock_429 = make_mock_response(429)

        with patch.object(
            client.session, "request", return_value=mock_429
        ):
            with pytest.raises(ZhihuRateLimitError, match="重试"):
                client.get_comments("12345", "article")


# ─── post_comment 测试 ──────────────────────────────────────────

class TestPostComment:
    """测试 post_comment 方法"""

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_target_url(self, mock_sleep) -> None:
        """发布评论应请求 https://api.zhihu.com/v4/comments"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(201, {"id": 9999})

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            result = client.post_comment("12345", "article", "测试回复")

        assert result is True
        call_args = mock_req.call_args
        assert call_args[0][1] == "https://api.zhihu.com/v4/comments"

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_includes_xsrf_header(self, mock_sleep) -> None:
        """发布评论请求头应包含 x-xsrftoken"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(200, {"id": 9999})

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            client.post_comment("12345", "article", "测试回复")

        call_kwargs = mock_req.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["x-xsrftoken"] == "test_xsrf_token_123"

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_includes_correct_payload(self, mock_sleep) -> None:
        """发布评论请求体应包含 object_id, object_type, content"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(200, {"id": 9999})

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            client.post_comment("12345", "article", "测试回复", parent_id="1001")

        call_kwargs = mock_req.call_args[1]
        payload = call_kwargs["json"]
        assert payload["object_id"] == "12345"
        assert payload["object_type"] == "article"
        assert payload["content"] == "测试回复"
        assert payload["parent_id"] == "1001"

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_success_returns_true(self, mock_sleep) -> None:
        """发布成功（200/201）应返回 True"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(200, {"id": 9999})

        with patch.object(client.session, "request", return_value=mock_resp):
            assert client.post_comment("12345", "article", "回复") is True

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_auth_failure_returns_false(self, mock_sleep) -> None:
        """发布时 401 应返回 False（不抛出异常）"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(401)

        with patch.object(client.session, "request", return_value=mock_resp):
            result = client.post_comment("12345", "article", "回复")

        assert result is False

    @patch("scripts.zhihu_client.time.sleep")
    def test_post_without_parent_id(self, mock_sleep) -> None:
        """不提供 parent_id 时，请求体不应包含 parent_id"""
        client = ZhihuClient(TEST_COOKIE)
        mock_resp = make_mock_response(200, {"id": 9999})

        with patch.object(client.session, "request", return_value=mock_resp) as mock_req:
            client.post_comment("12345", "article", "顶级评论回复")

        payload = mock_req.call_args[1]["json"]
        assert "parent_id" not in payload
