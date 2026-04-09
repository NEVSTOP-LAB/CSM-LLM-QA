"""
AI-002 骨架 / AI-010 实现: GitHub Issue 自动告警
参考: docs/plan/README.md § AI-010

功能：
- create_issue(): 调用 GitHub API 创建 Issue
- 告警场景：Cookie 失效、限流、连续失败、预算超限
- 防重复：检查已有同 title 的 open issue
"""

from __future__ import annotations
