# Pin 监控 - 功能规范（增量）

## MODIFIED Requirements

### Requirement: Pin 监控方式

系统 SHALL 通过每日审计的方式处理新增的 Pin 消息。

**变更说明**：移除实时轮询（PinMonitor），仅保留每日审计（DailyPinAuditor），简化系统并避免重复处理。

#### Scenario: 每日审计触发

- **WHEN** 系统时间到达每天 09:00
- **THEN** 自动触发昨日 Pin 审计
- **AND** 日志输出 "🔔 定时任务触发: 每日 Pin 审计"
- **AND** 获取昨日新增的所有 Pin 消息

#### Scenario: 昨日有新增 Pin

- **WHEN** 昨日有 N 条新增 Pin 消息
- **THEN** 逐条处理每条 Pin：
  - 归档到 Bitable（PIN_TABLE_ID）
  - 增加发送者的"被加精次数"
  - 写入精华文档（ESSENCE_DOC_TOKEN，如已配置）
  - 记录到已处理集合（避免重复）
- **AND** 处理完成后发送汇总卡片到群聊
- **AND** 卡片包含：日期、新增数量、每条 Pin 摘要

#### Scenario: 昨日无新增 Pin

- **WHEN** 昨日没有新的 Pin 消息
- **THEN** 不发送汇总卡片
- **AND** 日志输出 "[Pin] 昨日无新增 Pin"
- **AND** 不执行任何处理

#### Scenario: Pin 处理成功

- **WHEN** 单条 Pin 处理成功
- **THEN** Bitable 中新增 Pin 记录
- **AND** 发送者的"被加精次数" +1
- **AND** 活跃度分数重新计算
- **AND** 日志输出 "[Pin归档] ✅ Pin消息已归档到Bitable"

#### Scenario: Pin 处理失败

- **WHEN** 单条 Pin 处理失败（API 错误、网络问题等）
- **THEN** 记录错误日志
- **AND** 继续处理下一条 Pin
- **AND** 不中断整个审计流程

### Requirement: Pin 去重

系统 SHALL 确保同一条 Pin 不会被重复处理。

#### Scenario: 已处理的 Pin

- **WHEN** Pin 的 message_id 已在已处理集合中
- **THEN** 跳过该 Pin
- **AND** 日志输出 "[Pin] 消息已处理，跳过"

#### Scenario: 新 Pin 处理

- **WHEN** Pin 的 message_id 未处理过
- **THEN** 正常处理该 Pin
- **AND** 处理完成后将 message_id 加入已处理集合

#### Scenario: 持久化去重记录

- **WHEN** 程序重启
- **THEN** 从 `.processed_daily_pins.txt` 加载已处理的 message_id
- **AND** 继续追加新记录到文件

### Requirement: 月度归档

系统 SHALL 支持每月对 Pin 数据进行归档。

#### Scenario: 月度归档触发

- **WHEN** 系统时间到达每月 1 号 02:00
- **THEN** 自动触发月度归档
- **AND** 日志输出 "📦 开始执行月度归档"

#### Scenario: 归档到历史表

- **WHEN** 执行月度归档
- **THEN** 将上月的数据从活跃表复制到历史表
- **AND** 清空活跃表中的上月数据
- **AND** 日志输出 "✅ 归档完成" 和 "✅ 清空完成"

#### Scenario: 归档表未配置

- **WHEN** 环境变量 ARCHIVE_STATS_TABLE_ID 未设置
- **THEN** 跳过月度归档
- **AND** 日志输出 "[月度归档] ⚠️ ARCHIVE_STATS_TABLE_ID 未配置，跳过归档"

## REMOVED Requirements

### Requirement: PinMonitor 实时轮询

**Reason**:

1. 与 DailyPinAuditor 功能重叠，导致代码重复
2. 可能重复处理同一条 Pin（去重机制不一致）
3. 30 秒轮询占用 API 配额
4. 用户确认仅保留每日审计方式

**Migration**:

- 停止 `pin_monitor.py` 的 `PinMonitor` 后台线程
- 移除 `pin_scheduler.py` 中的以下调度代码：
  ```python
  # schedule.every(PIN_MONITOR_INTERVAL).seconds.do(
  #     pin_monitor.start_monitoring
  # ).tag('pin-monitor')
  ```
- 删除 `pin_monitor.py` 文件
- 移除环境变量 `PIN_MONITOR_INTERVAL`
- 所有 Pin 处理逻辑由 `pin_daily_audit.py` 的 `DailyPinAuditor` 统一处理

### Requirement: 实时 Pin 提醒

**Reason**: 移除实时轮询后，无法在 Pin 发生时立即提醒

**Migration**:

- 用户需适应从"实时提醒"改为"每日汇总"
- 每日 09:00 的汇总卡片提供完整的昨日 Pin 信息
- 如需实时提醒，可后续通过 Webhook 方式实现（不在本次优化范围）

### Requirement: Pin 首次运行标志

**Reason**: PinMonitor 使用 `is_first_run` 标志跳过历史 Pin，DailyPinAuditor 无此需求

**Migration**:

- 移除 `pin_monitor_first_run.txt` 文件（如果存在）
- DailyPinAuditor 始终处理昨日新增 Pin，无需首次运行特殊处理
