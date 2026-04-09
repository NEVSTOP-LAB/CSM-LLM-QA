# AI-012 实施记录：费用监控 — Token 计数与预算日报

## 状态：✅ 完成

## 实施内容

### CostTracker 类实现 (`scripts/cost_tracker.py`)
- `record(model, prompt_tokens, completion_tokens, cache_hit_tokens, usd_cost)` — 记录到 jsonl
- `get_daily_cost(target_date)` — 指定日期费用累计
- `get_daily_summary(target_date)` — 日报摘要（调用次数、tokens、费用）
- `update_monthly_summary()` — 月度汇总写入 cost_summary.json
- `print_daily_report()` — 输出费用报告到 stdout

## 测试结果
```
11 passed in 0.04s
```

覆盖：记录（4）、日费用（3）、日报摘要（2）、月度汇总（2）

## 验收标准
- [x] cost_log.jsonl 行数正确
- [x] 日费用累计计算正确
- [x] 月度汇总按月聚合
