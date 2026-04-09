# AI-010 实施记录：告警模块 — GitHub Issue 自动创建

## 状态：✅ 完成

## 实施内容

### AlertManager 类实现 (`scripts/alerting.py`)
- `create_issue(title, body, labels)` — 幂等创建 GitHub Issue
  - 检查同 title 的 open issue，避免重复
  - 无 token 时安全跳过
- 告警场景方法：
  - `alert_cookie_expired(error_code)` — Cookie 失效
  - `alert_rate_limited()` — 持续限流
  - `alert_budget_exceeded(cost, budget)` — 预算超限
  - `alert_consecutive_failures(count)` — 连续失败
- `record_health(status, details)` — 记录 Cookie 存活状态到 health.json

## 测试结果
```
12 passed in 0.18s
```

覆盖：Issue 创建（4）、告警场景（4）、健康状态记录（4）

## 验收标准
- [x] Cookie 失效时自动创建 GitHub Issue
- [x] 幂等不刷 issue
- [x] health.json 记录了 Cookie 状态
