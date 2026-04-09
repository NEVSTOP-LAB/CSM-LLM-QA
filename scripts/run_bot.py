"""
AI-002 骨架 / AI-009 实现: 主入口 — 串联所有模块的主流程
参考: docs/plan/README.md § AI-009

功能：
1. 加载配置，初始化所有模块
2. 每日处理量检查（max_new_comments_per_day）
3. 对每篇文章：拉取评论 → 前置过滤 → RAG → LLM → 写入 pending/
4. 检测真人新回复，调用 index_human_reply
5. ZhihuAuthError / BudgetExceededError 时创建 GitHub Issue 告警
6. 退出前 git commit（若有变更）
"""

from __future__ import annotations


def main() -> None:
    """主入口函数，由 GitHub Actions 或命令行调用"""
    raise NotImplementedError("AI-009: 待实现")


if __name__ == "__main__":
    main()
