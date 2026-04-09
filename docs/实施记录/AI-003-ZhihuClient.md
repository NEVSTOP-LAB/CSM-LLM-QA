# AI-003 实施记录：ZhihuClient — 读取与写入接口

## 状态：✅ 完成

## 实施内容

### 1. ZhihuClient 类实现 (`scripts/zhihu_client.py`)
- `ZhihuClient(cookie)` — 从 Cookie 初始化，自动提取 `_xsrf` CSRF token
- `get_comments(object_id, object_type, since_id)` — 评论读取
  - 支持 article（`/api/v4/articles/{id}/comments`）和 question（`/api/v4/answers/{id}/comments`）
  - 自动分页（`is_end=True` 停止）
  - 随机延迟 1~2 秒
  - 429 指数退避最多 3 次
- `post_comment(object_id, object_type, content, parent_id)` — 评论发布
  - 目标 URL: `https://api.zhihu.com/v4/comments`
  - Cookie + `x-xsrftoken` CSRF 认证
  - 失败返回 False（不抛异常）
- `Comment` dataclass: id, parent_id, content, author, created_time, is_author_reply
- `ZhihuAuthError` / `ZhihuRateLimitError` 异常类

### 2. 浏览器指纹
参考 zhihu-cli 设置了 User-Agent, Referer, sec-ch-ua 等请求头

## 测试结果
```
24 passed in 0.13s
```

测试覆盖：
- CSRF token 提取（3 tests）
- URL 构建（3 tests）
- 评论读取（4 tests: 单页/多页/问题类型/空列表）
- 认证错误（2 tests: 401/403）
- 限流重试（2 tests: 重试成功/超限）
- Comment 解析（3 tests: 基本字段/parent_id/默认值）
- 评论发布（7 tests: 成功/CSRF头/参数/parent_id/401/无xsrf/网络错误）

## 验收标准
- [x] get_comments 支持 article/question 类型
- [x] post_comment 调用正确端点并附加 CSRF 头
- [x] 单元测试全部通过
