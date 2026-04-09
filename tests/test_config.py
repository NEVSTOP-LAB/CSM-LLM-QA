"""
AI-002: 配置文件加载测试
参考: docs/plan/README.md § AI-002 验收标准

验证：
- config/articles.yaml 可被正确加载
- config/settings.yaml 可被正确加载
- 两个配置文件的必填字段存在
"""

import pytest


class TestArticlesConfig:
    """测试 config/articles.yaml 配置加载"""

    def test_articles_yaml_loads(self, articles_config: dict) -> None:
        """articles.yaml 应能被正确加载为字典"""
        assert articles_config is not None
        assert isinstance(articles_config, dict)

    def test_articles_key_exists(self, articles_config: dict) -> None:
        """articles.yaml 应包含 'articles' 顶层键"""
        assert "articles" in articles_config

    def test_articles_is_list(self, articles_config: dict) -> None:
        """articles 应为列表"""
        assert isinstance(articles_config["articles"], list)

    def test_article_required_fields(self, articles_config: dict) -> None:
        """每个 article 条目应包含 id, title, url, type 必填字段"""
        required_fields = {"id", "title", "url", "type"}
        for article in articles_config["articles"]:
            for field in required_fields:
                assert field in article, f"文章条目缺少必填字段: {field}"

    def test_article_type_valid(self, articles_config: dict) -> None:
        """article type 应为 'article' 或 'question'"""
        valid_types = {"article", "question"}
        for article in articles_config["articles"]:
            assert article["type"] in valid_types, (
                f"无效的文章类型: {article['type']}，应为 {valid_types}"
            )


class TestSettingsConfig:
    """测试 config/settings.yaml 配置加载"""

    def test_settings_yaml_loads(self, settings_config: dict) -> None:
        """settings.yaml 应能被正确加载为字典"""
        assert settings_config is not None
        assert isinstance(settings_config, dict)

    def test_bot_section_exists(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'bot' 配置段"""
        assert "bot" in settings_config

    def test_bot_required_fields(self, settings_config: dict) -> None:
        """bot 配置段应包含必填字段"""
        bot = settings_config["bot"]
        required = [
            "check_interval_hours",
            "max_new_comments_per_run",
            "max_new_comments_per_day",
            "llm_budget_usd_per_day",
        ]
        for field in required:
            assert field in bot, f"bot 配置缺少必填字段: {field}"

    def test_llm_section_exists(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'llm' 配置段"""
        assert "llm" in settings_config

    def test_llm_required_fields(self, settings_config: dict) -> None:
        """llm 配置段应包含必填字段"""
        llm = settings_config["llm"]
        required = ["base_url", "model", "max_tokens", "temperature"]
        for field in required:
            assert field in llm, f"llm 配置缺少必填字段: {field}"

    def test_rag_section_exists(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'rag' 配置段"""
        assert "rag" in settings_config

    def test_rag_required_fields(self, settings_config: dict) -> None:
        """rag 配置段应包含必填字段"""
        rag = settings_config["rag"]
        required = [
            "embedding_model",
            "use_online_embedding",
            "top_k",
            "similarity_threshold",
            "history_turns",
        ]
        for field in required:
            assert field in rag, f"rag 配置缺少必填字段: {field}"

    def test_vector_store_section(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'vector_store' 配置段"""
        assert "vector_store" in settings_config
        vs = settings_config["vector_store"]
        assert "backend" in vs
        assert "max_size_mb" in vs

    def test_review_section(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'review' 配置段"""
        assert "review" in settings_config
        review = settings_config["review"]
        assert "manual_mode" in review
        # 默认应为 true（pending/ 模式）
        assert review["manual_mode"] is True

    def test_filter_section(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'filter' 配置段"""
        assert "filter" in settings_config
        f = settings_config["filter"]
        assert "max_comment_tokens" in f
        assert "spam_keywords" in f
        assert "dedup_window_minutes" in f

    def test_alerting_section(self, settings_config: dict) -> None:
        """settings.yaml 应包含 'alerting' 配置段"""
        assert "alerting" in settings_config
        alerting = settings_config["alerting"]
        assert "github_issue" in alerting
        assert "consecutive_fail_limit" in alerting
