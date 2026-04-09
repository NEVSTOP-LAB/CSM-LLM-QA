"""
AI-009: 主入口 — 串联所有模块的主流程 (MVP 版 pending/ 模式)
参考: docs/plan/README.md § AI-009

功能：
1. 加载配置（config/settings.yaml + config/articles.yaml）
2. 初始化所有模块（ZhihuClient, RAGRetriever, LLMClient, ThreadManager, CostTracker）
3. 读取 seen_ids.json，过滤已处理评论
4. 对每篇文章：拉取评论 → 前置过滤 → RAG → LLM → 写入 pending/
5. 检测真人新回复，调用 index_human_reply
6. ZhihuAuthError / BudgetExceededError 时创建 GitHub Issue 告警
7. 退出前保存状态（seen_ids.json, cost_log.json）

运行模式：
- manual_mode=True (默认): 生成的回复写入 pending/ 目录，需人工审核
- manual_mode=False: 直接调用 post_comment 发布（验证通过后启用）
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# 确保 scripts 目录在 import 路径中
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.zhihu_client import ZhihuClient, ZhihuAuthError, Comment
from scripts.rag_retriever import RAGRetriever
from scripts.llm_client import LLMClient, BudgetExceededError
from scripts.thread_manager import ThreadManager
from scripts.comment_filter import should_skip, truncate_comment, reset_dedup_cache
from scripts.alerting import create_alert_issue
from scripts.cost_tracker import CostTracker

# ─── 日志配置 ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_bot")


# ─── 状态文件路径 ──────────────────────────────────────────────

SEEN_IDS_PATH = ROOT_DIR / "data" / "seen_ids.json"
COST_LOG_PATH = ROOT_DIR / "data" / "cost_log.json"
WIKI_HASH_PATH = ROOT_DIR / "data" / "wiki_hash.json"


def load_config() -> tuple[dict, dict]:
    """
    加载配置文件
    参考: docs/plan/README.md § AI-009 第 1 点

    Returns:
        (settings, articles) 元组
    """
    settings_path = ROOT_DIR / "config" / "settings.yaml"
    articles_path = ROOT_DIR / "config" / "articles.yaml"

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    with open(articles_path, "r", encoding="utf-8") as f:
        articles_config = yaml.safe_load(f)

    return settings, articles_config


def load_seen_ids() -> dict:
    """加载已处理评论 ID"""
    if SEEN_IDS_PATH.exists():
        with open(SEEN_IDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": {}, "last_run": None}


def save_seen_ids(seen_ids: dict) -> None:
    """保存已处理评论 ID"""
    SEEN_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(seen_ids, f, ensure_ascii=False, indent=2)


def write_pending_reply(
    article_id: str,
    comment: Comment,
    reply_text: str,
    tokens: int,
    model: str,
) -> Path:
    """
    将生成的回复写入 pending/ 目录（人工审核模式）
    参考: docs/plan/README.md § AI-009 第 4 点 — pending/ 模式

    Args:
        article_id: 文章 ID
        comment: 原始评论
        reply_text: 生成的回复
        tokens: 使用的 token 数
        model: 模型名称

    Returns:
        pending 文件路径
    """
    pending_dir = ROOT_DIR / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{now}_{article_id}_{comment.id}.md"
    filepath = pending_dir / filename

    content = (
        f"---\n"
        f"article_id: \"{article_id}\"\n"
        f"comment_id: \"{comment.id}\"\n"
        f"comment_author: \"{comment.author}\"\n"
        f"parent_id: {json.dumps(comment.parent_id)}\n"
        f"model: \"{model}\"\n"
        f"tokens: {tokens}\n"
        f"generated_at: \"{datetime.now(timezone.utc).isoformat()}\"\n"
        f"status: pending\n"
        f"---\n\n"
        f"## 原始评论\n\n"
        f"> {comment.content}\n\n"
        f"## 生成的回复\n\n"
        f"{reply_text}\n"
    )

    filepath.write_text(content, encoding="utf-8")
    logger.info("回复已写入 pending/: %s", filename)
    return filepath


def process_article(
    article: dict,
    zhihu_client: ZhihuClient,
    rag: RAGRetriever,
    llm: LLMClient,
    thread_mgr: ThreadManager,
    cost_tracker: CostTracker,
    seen_ids: dict,
    settings: dict,
) -> int:
    """
    处理单篇文章：拉取评论 → 过滤 → RAG → LLM → pending/
    参考: docs/plan/README.md § AI-009 第 4 点

    Args:
        article: 文章配置
        zhihu_client: 知乎客户端
        rag: RAG 检索器
        llm: LLM 客户端
        thread_mgr: 线程管理器
        cost_tracker: 费用追踪
        seen_ids: 已处理 ID
        settings: 全局配置

    Returns:
        本次处理的评论数
    """
    article_id = article["id"]
    article_type = article.get("type", "article")
    article_meta = {"title": article.get("title", ""), "url": article.get("url", "")}

    # 获取已处理的最大评论 ID
    article_seen = seen_ids.get("articles", {})
    since_id = article_seen.get(article_id)

    logger.info("处理文章: %s (%s) since_id=%s", article_meta["title"], article_id, since_id)

    # 拉取新评论
    # 参考: docs/plan/README.md § AI-003 — get_comments
    comments = zhihu_client.get_comments(article_id, article_type, since_id=since_id)

    if not comments:
        logger.info("无新评论: %s", article_id)
        return 0

    # 每次处理上限
    max_per_run = settings.get("bot", {}).get("max_new_comments_per_run", 20)
    comments = comments[:max_per_run]

    processed = 0
    model = settings.get("llm", {}).get("model", "deepseek-chat")
    review_settings = settings.get("review", {})
    manual_mode = review_settings.get("manual_mode", True)
    rag_settings = settings.get("rag", {})
    top_k = rag_settings.get("top_k", 3)
    threshold = rag_settings.get("similarity_threshold", 0.72)

    for comment in comments:
        # 检测真人新回复 → 索引到 reply_index
        # 参考: docs/plan/README.md § AI-009 第 5 点
        if comment.is_author_reply:
            logger.info("检测到真人回复: comment_id=%s", comment.id)
            # 需要找到对应的问题
            if comment.parent_id:
                # 尝试从已有线程中获取上下文
                rag.index_human_reply(
                    question=f"(parent_id: {comment.parent_id})",
                    reply=comment.content,
                    article_id=article_id,
                    thread_id=comment.parent_id,
                )
                # 记录到线程
                root_comment_dict = {
                    "id": comment.parent_id,
                    "author": "unknown",
                    "content": "",
                    "created_time": comment.created_time,
                }
                thread_path = thread_mgr.get_or_create_thread(
                    article_id, root_comment_dict, article_meta
                )
                thread_mgr.append_turn(
                    thread_path,
                    author=comment.author,
                    content=comment.content,
                    is_human=True,
                    comment_id=comment.id,
                )
            continue

        # 前置过滤
        # 参考: docs/plan/README.md § AI-008
        skip, reason = should_skip(comment, settings)
        if skip:
            logger.info("跳过评论 %s: %s", comment.id, reason)
            continue

        # 截断超长评论
        filter_settings = settings.get("filter", {})
        max_tokens = filter_settings.get("max_comment_tokens", 500)
        comment_text, was_truncated = truncate_comment(comment.content, max_tokens)

        # 创建/获取线程
        root_id = comment.parent_id or comment.id
        root_comment_dict = {
            "id": root_id,
            "author": comment.author,
            "content": comment_text,
            "created_time": comment.created_time,
        }
        thread_path = thread_mgr.get_or_create_thread(
            article_id, root_comment_dict, article_meta
        )

        # 记录用户评论到线程
        is_followup = comment.parent_id is not None
        thread_mgr.append_turn(
            thread_path,
            author=comment.author,
            content=comment_text,
            comment_id=comment.id,
            is_followup=is_followup,
        )

        # RAG 检索
        # 参考: docs/plan/README.md § AI-005 — retrieve
        context_chunks = rag.retrieve(comment_text, k=top_k, threshold=threshold)

        # 构建历史上下文（追问场景）
        history_turns = rag_settings.get("history_turns", 6)
        history_messages = thread_mgr.build_context_messages(
            thread_path, max_turns=history_turns
        )
        # 去掉最后一条（就是刚追加的当前评论）
        if history_messages and len(history_messages) > 1:
            history_messages = history_messages[:-1]
        else:
            history_messages = None

        # 生成回复
        # 参考: docs/plan/README.md § AI-006 — generate_reply
        article_summary = article_meta.get("title", "")
        reply_text, tokens_used = llm.generate_reply(
            comment=comment_text,
            context_chunks=context_chunks,
            article_summary=article_summary,
            history_messages=history_messages,
        )

        # 记录费用
        cost_tracker.record_call(
            model=model,
            prompt_tokens=tokens_used,
            completion_tokens=0,
            cost_usd=llm.daily_cost,
            article_id=article_id,
            comment_id=comment.id,
        )

        # 写入线程
        thread_mgr.append_turn(
            thread_path,
            author="bot",
            content=reply_text,
            model=model,
            tokens=tokens_used,
        )

        # 根据模式处理回复
        if manual_mode:
            # pending/ 模式
            write_pending_reply(article_id, comment, reply_text, tokens_used, model)
        else:
            # 自动发布模式
            # 参考: docs/plan/README.md § AI-014
            success = zhihu_client.post_comment(
                article_id, article_type, reply_text,
                parent_id=comment.id,
            )
            if not success:
                # 发布失败，降级写入 pending/
                write_pending_reply(article_id, comment, reply_text, tokens_used, model)

        processed += 1

        # 更新 seen_id
        if "articles" not in seen_ids:
            seen_ids["articles"] = {}
        current_max = seen_ids["articles"].get(article_id, "0")
        if comment.id > current_max:
            seen_ids["articles"][article_id] = comment.id

    logger.info("文章 %s 处理完成: %d 条评论", article_id, processed)
    return processed


def main() -> None:
    """
    主入口函数，由 GitHub Actions 或命令行调用
    参考: docs/plan/README.md § AI-009
    """
    logger.info("=" * 60)
    logger.info("Zhihu CSM Reply Bot 启动")
    logger.info("=" * 60)

    # 1. 加载配置
    settings, articles_config = load_config()
    articles = articles_config.get("articles", [])
    logger.info("加载配置完成: %d 篇文章待监控", len(articles))

    # 2. 初始化模块
    cookie = os.environ.get("ZHIHU_COOKIE", "")
    if not cookie:
        logger.error("缺少 ZHIHU_COOKIE 环境变量")
        create_alert_issue("auth_failure", "ZHIHU_COOKIE 环境变量为空")
        sys.exit(1)

    try:
        zhihu_client = ZhihuClient(cookie)
    except ValueError as e:
        logger.error("ZhihuClient 初始化失败: %s", e)
        create_alert_issue("auth_failure", str(e))
        sys.exit(1)

    # RAG 检索器
    wiki_dir = str(ROOT_DIR / "csm-wiki")
    vector_store_dir = str(ROOT_DIR / "data" / "vector_store")
    reply_index_dir = str(ROOT_DIR / "data" / "reply_index")
    rag_settings = settings.get("rag", {})
    use_online = rag_settings.get("use_online_embedding", False)

    rag = RAGRetriever(
        wiki_dir=wiki_dir,
        vector_store_dir=vector_store_dir,
        reply_index_dir=reply_index_dir,
        use_online_embedding=use_online,
        wiki_hash_path=str(WIKI_HASH_PATH),
    )

    # 同步 Wiki 索引
    updated = rag.sync_wiki()
    logger.info("Wiki 同步完成: %d 个文件更新", updated)

    # LLM 客户端
    llm_settings = settings.get("llm", {})
    bot_settings = settings.get("bot", {})
    llm = LLMClient(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", llm_settings.get("base_url", "")),
        model=os.environ.get("LLM_MODEL", llm_settings.get("model", "deepseek-chat")),
        max_tokens=llm_settings.get("max_tokens", 250),
        temperature=llm_settings.get("temperature", 0.7),
        budget_usd_per_day=bot_settings.get("llm_budget_usd_per_day", 0.50),
    )

    # 线程管理器
    thread_mgr = ThreadManager(archive_dir=str(ROOT_DIR / "archive"))

    # 费用追踪
    cost_tracker = CostTracker(log_path=str(COST_LOG_PATH))

    # 3. 加载已处理 ID
    seen_ids = load_seen_ids()

    # 4. 处理每篇文章
    total_processed = 0
    consecutive_failures = 0
    max_consecutive_fail = settings.get("alerting", {}).get("consecutive_fail_limit", 3)
    max_per_day = bot_settings.get("max_new_comments_per_day", 100)

    # 重置过滤器缓存
    reset_dedup_cache()

    for article in articles:
        try:
            # 每日上限检查
            if total_processed >= max_per_day:
                logger.warning("已达每日处理上限 (%d)，停止处理", max_per_day)
                break

            count = process_article(
                article, zhihu_client, rag, llm,
                thread_mgr, cost_tracker, seen_ids, settings,
            )
            total_processed += count
            consecutive_failures = 0

        except ZhihuAuthError as e:
            # Cookie 失效 → 创建告警并退出
            # 参考: docs/plan/README.md § AI-009 第 6 点
            logger.error("知乎认证失败: %s", e)
            create_alert_issue("auth_failure", str(e))
            break

        except BudgetExceededError as e:
            # 预算超限 → 创建告警并退出
            logger.error("LLM 预算超限: %s", e)
            create_alert_issue("budget_exceeded", str(e))
            break

        except Exception as e:
            logger.error("处理文章 %s 时异常: %s", article.get("id", "?"), e, exc_info=True)
            consecutive_failures += 1

            if consecutive_failures >= max_consecutive_fail:
                logger.error("连续失败 %d 次，暂停处理", consecutive_failures)
                create_alert_issue(
                    "consecutive_fail",
                    f"连续失败 {consecutive_failures} 次，最后错误: {e}",
                )
                break

    # 5. 保存状态
    seen_ids["last_run"] = datetime.now(timezone.utc).isoformat()
    save_seen_ids(seen_ids)
    cost_tracker.save_to_file()

    # 6. 输出汇总
    summary = cost_tracker.get_daily_summary()
    logger.info("=" * 60)
    logger.info("运行完成: 处理 %d 条评论", total_processed)
    logger.info("今日费用: $%.6f (%d 次调用)", summary["total_cost_usd"], summary["call_count"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
