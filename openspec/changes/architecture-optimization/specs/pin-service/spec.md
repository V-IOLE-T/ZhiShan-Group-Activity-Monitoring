# Pin 处理服务 - 功能规范

## ADDED Requirements

### Requirement: 获取 Pin 消息列表

PinService SHALL 提供获取群组内所有 Pin 消息列表的功能。

#### Scenario: 成功获取 Pin 列表

- **WHEN** 调用 `PinService.get_pinned_messages(chat_id)`
- **THEN** 返回 Pin 消息列表，每个包含 message_id、operator_id、create_time
- **AND** 日志输出 "[Pin] 获取到 N 条 Pin 消息"

#### Scenario: API 调用失败

- **WHEN** 飞书 API 返回错误
- **THEN** 返回空列表
- **AND** 日志输出 "[Pin] ❌ 获取 Pin 列表失败"

#### Scenario: 分页处理

- **WHEN** 群内 Pin 数量超过 100 条（API 单页限制）
- **THEN** 自动分页获取所有 Pin
- **AND** 合并返回完整列表

### Requirement: 获取 Pin 消息详情

PinService SHALL 根据 message_id 获取完整的消息详情，包括内容、附件、发送者信息。

#### Scenario: 获取文本消息详情

- **WHEN** 调用 `PinService.get_message_detail(message_id)` 获取文本 Pin
- **THEN** 返回包含消息内容、发送者、时间戳的字典
- **AND** 提取纯文本内容（移除富文本标记）

#### Scenario: 获取带附件的消息详情

- **WHEN** Pin 消息包含图片或文件附件
- **THEN** 返回包含 file_key 的信息
- **AND** 标记附件类型（image/file）

#### Scenario: 消息不存在

- **WHEN** message_id 对应的消息已被删除
- **THEN** 返回 `None`
- **AND** 日志输出 "[Pin] ⚠️ 消息已不存在: {message_id}"

### Requirement: 附件转存

PinService SHALL 支持 Pin 消息中的附件转存到多维表格。

#### Scenario: 图片转存成功

- **WHEN** Pin 消息包含图片附件
- **THEN** 下载图片并上传到 Bitable
- **AND** 返回 file_token
- **AND** 更新 Pin 记录的附件字段

#### Scenario: 文件转存成功

- **WHEN** Pin 消息包含文件附件（PDF、DOCX 等）
- **THEN** 下载文件并上传到 Bitable
- **AND** 返回 file_token

#### Scenario: 附件下载失败

- **WHEN** 附件下载失败（文件已删除或网络错误）
- **THEN** 记录警告日志
- **AND** 继续处理其他内容，不中断整个流程

#### Scenario: 附件过大

- **WHEN** 附件大小超过 10MB
- **THEN** 跳过转存
- **AND** 日志输出 "[Pin] ⚠️ 附件过大，跳过转存"

### Requirement: 用户信息获取

PinService SHALL 统一获取用户昵称和群备注的功能，使用缓存优化。

#### Scenario: 从缓存获取用户名

- **WHEN** 用户信息已在缓存中（ThreadSafeLRUCache，容量500）
- **THEN** 直接返回缓存数据，不调用 API
- **AND** 响应时间 < 10ms

#### Scenario: 缓存未命中，调用 API

- **WHEN** 用户信息不在缓存中
- **THEN** 调用飞书 API 获取用户信息
- **AND** 更新缓存
- **AND** 返回用户昵称（优先返回群备注）

#### Scenario: 用户不存在

- **WHEN** 用户已退出群组或被删除
- **THEN** 返回 "未知用户"
- **AND** 日志输出 "[Pin] ⚠️ 获取用户信息失败"

#### Scenario: operator_id 格式兼容

- **WHEN** operator_id 可能是字符串或字典格式
- **THEN** 自动解析两种格式
- **AND** 正确提取 user_id

### Requirement: Bitable 归档

PinService SHALL 将 Pin 消息归档到专用的 Pin 归档表（PIN_TABLE_ID）。

#### Scenario: 归档成功

- **WHEN** 调用 `PinService.archive_to_bitable(pin_info)`
- **THEN** 在 Pin 表中创建新记录
- **AND** 字段包含：Pin 消息 ID、发送者、操作人、时间、内容、附件
- **AND** 日志输出 "[Pin归档] ✅ Pin消息已归档到Bitable"

#### Scenario: PIN_TABLE_ID 未配置

- **WHEN** 环境变量 PIN_TABLE_ID 未设置
- **THEN** 跳过 Bitable 归档
- **AND** 日志输出 "[Pin] ⚠️ PIN_TABLE_ID 未配置，跳过 Bitable 归档"
- **AND** 不抛出异常

#### Scenario: API 调用失败

- **WHEN** Bitable API 返回错误
- **THEN** 记录错误日志
- **AND** 继续处理后续逻辑

### Requirement: 被加精次数统计

PinService SHALL 增加用户的"被加精次数"并重新计算活跃度分数。

#### Scenario: 增加被加精次数

- **WHEN** 用户的消息被 Pin
- **THEN** 该用户的"被加精次数"字段 +1
- **AND** "活跃度分数"根据权重重新计算
- **AND** 更新 Bitable 中的用户记录

#### Scenario: 活跃度表不存在用户

- **WHEN** 被加精的用户不在活跃度表中
- **THEN** 创建新用户记录
- **AND** 初始化"被加精次数"为 1

### Requirement: 精华文档写入

PinService SHALL 支持将 Pin 消息写入精华文档（ESSENCE_DOC_TOKEN）。

#### Scenario: 写入精华文档成功

- **WHEN** 环境变量 ESSENCE_DOC_TOKEN 已配置
- **THEN** 在精华文档中添加新 Block
- **AND** 格式：发送者、时间、消息内容
- **AND** 日志输出 "[Pin] ✅ 已写入精华文档"

#### Scenario: ESSENCE_DOC_TOKEN 未配置

- **WHEN** 环境变量 ESSENSE_DOC_TOKEN 未设置
- **THEN** 跳过精华文档写入
- **AND** 不抛出异常

### Requirement: Pin 去重

PinService SHALL 确保同一条 Pin 消息不会被重复处理。

#### Scenario: 已处理的消息

- **WHEN** message_id 已在已处理集合中
- **THEN** 跳过该消息
- **AND** 日志输出 "[Pin] 消息已处理，跳过"

#### Scenario: 新消息处理

- **WHEN** message_id 未处理过
- **THEN** 正常处理该消息
- **AND** 处理完成后将 message_id 加入已处理集合

#### Scenario: 持久化去重记录

- **WHEN** 程序重启
- **THEN** 从 `.processed_daily_pins.txt` 加载已处理的消息 ID
- **AND** 继续追加新记录到文件

### Requirement: 每日审计触发

PinService SHALL 在每天 09:00 自动触发昨日 Pin 审计。

#### Scenario: 定时触发

- **WHEN** 系统时间到达 09:00
- **THEN** 自动执行昨日 Pin 审计
- **AND** 日志输出 "🔔 定时任务触发: 每日 Pin 审计"

#### Scenario: 昨日无新增 Pin

- **WHEN** 昨日没有新的 Pin 消息
- **THEN** 不发送汇总卡片
- **AND** 日志输出 "[Pin] 昨日无新增 Pin"

#### Scenario: 昨日有新增 Pin

- **WHEN** 昨日有 N 条新增 Pin
- **THEN** 处理所有昨日新增 Pin
- **AND** 发送汇总卡片到群聊
- **AND** 卡片包含：日期、数量、每条 Pin 摘要

## REMOVED Requirements

### Requirement: PinMonitor 实时轮询

**Reason**: 与 DailyPinAuditor 功能重叠，可能导致重复处理，用户确认仅保留每日审计
**Migration**:

- 停止 `pin_monitor.py` 的后台线程
- 移除 `pin_scheduler.py` 中的 PinMonitor 调度配置
- 删除 `pin_monitor.py` 文件
- 所有 Pin 处理逻辑合并到 `pin_daily_audit.py` 和 `PinService`

### Requirement: 30秒轮询间隔

**Reason**: 实时轮询功能已移除
**Migration**:

- 移除环境变量 `PIN_MONITOR_INTERVAL`
- 移除配置项 `PIN_MONITOR_INTERVAL`
