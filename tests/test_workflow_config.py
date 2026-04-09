"""
AI-004: GitHub Actions Workflow 配置测试
参考: docs/plan/README.md § AI-004 测试要求

验证：
- workflow YAML 可正确解析
- cron 定时触发配置存在
- secrets 引用正确
- permissions 配置正确
- 必要的 steps 存在
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def workflow_config(project_root: Path) -> dict:
    """加载 .github/workflows/bot.yml"""
    workflow_path = project_root / ".github" / "workflows" / "bot.yml"
    assert workflow_path.exists(), "bot.yml 文件不存在"
    with open(workflow_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_triggers(workflow_config: dict) -> dict:
    """获取 workflow 触发配置（处理 YAML 'on' → True 的特殊情况）"""
    # PyYAML 将 YAML 的 'on' 键解析为布尔值 True
    return workflow_config.get("on") or workflow_config.get(True, {})


class TestWorkflowTriggers:
    """测试 workflow 触发条件"""

    def test_schedule_exists(self, workflow_config: dict) -> None:
        """应配置 schedule 定时触发"""
        triggers = _get_triggers(workflow_config)
        assert triggers, "未找到触发配置（on 或 True 键）"
        assert "schedule" in triggers

    def test_cron_expression(self, workflow_config: dict) -> None:
        """cron 表达式应为每6小时"""
        triggers = _get_triggers(workflow_config)
        schedules = triggers["schedule"]
        assert len(schedules) >= 1
        cron = schedules[0]["cron"]
        # 验证包含多个小时点（每6小时）
        assert "2,8,14,20" in cron or "*/6" in cron

    def test_workflow_dispatch(self, workflow_config: dict) -> None:
        """应支持手动触发 (workflow_dispatch)"""
        triggers = _get_triggers(workflow_config)
        assert "workflow_dispatch" in triggers


class TestWorkflowPermissions:
    """测试 workflow 权限配置"""

    def test_contents_write(self, workflow_config: dict) -> None:
        """应有 contents: write 权限（推送存档）"""
        permissions = workflow_config.get("permissions", {})
        assert permissions.get("contents") == "write"

    def test_issues_write(self, workflow_config: dict) -> None:
        """应有 issues: write 权限（创建告警 Issue）"""
        permissions = workflow_config.get("permissions", {})
        assert permissions.get("issues") == "write"


class TestWorkflowSteps:
    """测试 workflow 步骤配置"""

    def test_job_exists(self, workflow_config: dict) -> None:
        """应包含 check-and-reply job"""
        assert "jobs" in workflow_config
        assert "check-and-reply" in workflow_config["jobs"]

    def test_runs_on_ubuntu(self, workflow_config: dict) -> None:
        """应在 ubuntu-latest 上运行"""
        job = workflow_config["jobs"]["check-and-reply"]
        assert job["runs-on"] == "ubuntu-latest"

    def test_checkout_step(self, workflow_config: dict) -> None:
        """应包含 actions/checkout 步骤"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        assert len(checkout_steps) >= 1

    def test_python_setup_step(self, workflow_config: dict) -> None:
        """应包含 actions/setup-python 步骤"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        python_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-python")]
        assert len(python_steps) >= 1

    def test_pip_cache_step(self, workflow_config: dict) -> None:
        """应包含 pip 缓存步骤"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        cache_steps = [
            s for s in steps
            if s.get("uses", "").startswith("actions/cache")
            and "pip" in str(s.get("with", {}).get("path", ""))
        ]
        assert len(cache_steps) >= 1

    def test_huggingface_cache_step(self, workflow_config: dict) -> None:
        """应包含 HuggingFace 模型缓存步骤"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        hf_steps = [
            s for s in steps
            if s.get("uses", "").startswith("actions/cache")
            and "huggingface" in str(s.get("with", {}).get("path", ""))
        ]
        assert len(hf_steps) >= 1

    def test_run_bot_step(self, workflow_config: dict) -> None:
        """应包含运行 scripts/run_bot.py 的步骤"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        bot_steps = [
            s for s in steps
            if "run_bot.py" in str(s.get("run", ""))
        ]
        assert len(bot_steps) >= 1


class TestWorkflowSecrets:
    """测试 secrets 引用"""

    def test_secrets_referenced(self, workflow_config: dict) -> None:
        """workflow 中应引用必要的 secrets"""
        yaml_str = yaml.dump(workflow_config)
        required_secrets = ["ZHIHU_COOKIE", "LLM_API_KEY", "GITHUB_TOKEN"]
        for secret in required_secrets:
            assert secret in yaml_str, f"缺少 secret 引用: {secret}"

    def test_git_commit_step(self, workflow_config: dict) -> None:
        """应包含 git commit+push 步骤，且包含 [skip ci]"""
        steps = workflow_config["jobs"]["check-and-reply"]["steps"]
        commit_steps = [
            s for s in steps
            if "git config" in str(s.get("run", "")) and "commit" in str(s.get("run", ""))
        ]
        assert len(commit_steps) >= 1
        # 验证包含 [skip ci]
        assert "[skip ci]" in str(commit_steps[0].get("run", ""))
