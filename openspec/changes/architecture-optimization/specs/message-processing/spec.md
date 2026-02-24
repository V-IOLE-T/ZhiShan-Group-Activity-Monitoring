# 消息处理 - 功能规范（增量）

## MODIFIED Requirements

### Requirement: 单聊消息处理
系统 SHALL 处理用户与机器人的单聊消息，支持文档链接提取和卡片生成。

**变更说明**：保持同步处理模式，直接生成图片并回复用户，MCP 超时增加到 30 秒并添加重试机制。

#### Scenario: 收到文档链接 - 同步处理
- **WHEN** 用户在单聊中发送飞书文档链接（docx/doc/wiki）
- **THEN** 提取文档 Token
- **AND** 调用 MCP 获取文档内容（30秒超时，带重试）
- **AND** 使用淡绿色样式生成卡片图片
- **AND** 直接发送图片回复给用户
- **AND** 总耗时视 MCP 调用而定（通常 10-30 秒）

#### Scenario: 收到纯文本消息
- **WHEN** 用户在单聊中发送纯文本（非文档链接）
- **THEN** 直接渲染为图片
- **AND** 发送图片回复
- **AND** 总耗时 < 3 秒

#### Scenario: MCP 调用超时 - 降级处理
- **WHEN** MCP 调用超过 30 秒未返回
- **THEN** 停止等待，返回降级响应
- **AND** 降级响应为纯文本卡片（包含文档标题和链接）
- **AND** 日志输出 "[单聊] ⚠️ MCP 调用超时，使用降级方案"

#### Scenario: MCP 调用失败 - 重试机制
- **WHEN** MCP 调用因网络错误失败
- **THEN** 自动重试 1 次（间隔 2 秒）
- **AND** 重试成功后正常生成图片
- **AND** 重试失败则降级为纯文本卡片

#### Scenario: 文档无权限
- **WHEN** 机器人无目标文档的阅读权限
- **THEN** 同步返回错误提示
- **AND** 提示内容："❌ 获取文档内容失败，请检查机器人是否拥有该文档的阅读权限。"

#### Scenario: 非文档链接
- **WHEN** 用户发送非飞书文档链接（如网页链接）
- **THEN** 返回提示："请发送飞书文档链接（docx/doc/wiki）"
- **AND** 不执行任何处理

## Property-Based Testing Properties

### [INVARIANT] Degradation Fallback
**Property**: MCP failure always produces valid response (never crashes)
- **FALSIFICATION STRATEGY**: Inject various MCP failures:
  - Timeout (> 30s): return plain text card
  - Network error: retry once, then degrade
  - 503 error: return text with error message
  - Always return valid response to user

### [IDEMPOTENCY] Message Deduplication
**Property**: Processing same `event_id` twice yields single response
- **FALSIFICATION STRATEGY**: Duplicate events from webhook:
  - First event: processed, response sent
  - Second event (same `event_id`): skipped, no response
  - Cache contains exactly one entry per `event_id`

## REMOVED Requirements

### Requirement: 两阶段异步处理
**Reason**: 用户选择保持同步处理模式，直接生成图片并回复，不需要占位图和后台线程

**Migration**:
- 删除 `reply_card/placeholder_generator.py` 文件
- 简化 `reply_card/processor.py` 的 `process_and_reply()` 方法
- 删除 `_MAX_ASYNC_THREADS` 和 `_thread_pool` 线程池
- MCP 超时从 10 秒增加到 30 秒
- 添加重试机制（最多 2 次，间隔 2 秒）

### Requirement: 长连接事件循环保护
**Reason**: 同步处理模式下，不再需要特别保护长连接事件循环

### Requirement: 后台线程管理
**Reason**: 同步处理模式下，不再需要后台线程管理

### Requirement: 占位图设计
**Reason**: 同步处理模式下，不再需要占位图
