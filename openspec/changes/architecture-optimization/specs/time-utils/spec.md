# 时间处理工具集 - 功能规范

## ADDED Requirements

### Requirement: 毫秒时间戳格式化

系统 SHALL 提供将飞书 API 返回的毫秒时间戳转换为可读字符串的函数。

#### Scenario: 标准格式化

- **WHEN** 调用 `format_timestamp_ms(1709260800000)`
- **THEN** 返回 "2024-03-01 12:00:00"
- **AND** 格式为 "YYYY-MM-DD HH:MM:SS"

#### Scenario: 当前时间格式化

- **WHEN** 调用 `format_timestamp_ms(get_current_timestamp_ms())`
- **THEN** 返回当前时间的格式化字符串
- **AND** 精确到秒

#### Scenario: 无效时间戳

- **WHEN** 传入 None 或负数
- **THEN** 返回 "未知时间"
- **AND** 不抛出异常

### Requirement: 秒时间戳格式化

系统 SHALL 支持秒级时间戳的格式化。

#### Scenario: 秒时间戳转换

- **WHEN** 调用 `format_timestamp(1709260800)`
- **THEN** 返回 "2024-03-01 12:00:00"
- **AND** 自动识别秒级时间戳

#### Scenario: 字符串时间戳

- **WHEN** 传入字符串类型的时间戳 "1709260800"
- **THEN** 自动转换并格式化
- **AND** 返回正确结果

### Requirement: 月份计算

系统 SHALL 提供月份相关的计算函数。

#### Scenario: 获取当前月份

- **WHEN** 调用 `get_current_month()`
- **THEN** 返回 "2024-03"
- **AND** 格式为 "YYYY-MM"

#### Scenario: 获取上个月

- **WHEN** 调用 `get_previous_month()`
- **AND** 当前月份是 2024-03
- **THEN** 返回 "2024-02"

#### Scenario: 跨年处理

- **WHEN** 当前月份是 2024-01
- **AND** 调用 `get_previous_month()`
- **THEN** 返回 "2023-12"

#### Scenario: 获取月份范围

- **WHEN** 调用 `get_month_range("2024-03")`
- **THEN** 返回该月的第一天和最后一天的时间戳
- **AND** 格式为 `(start_timestamp_ms, end_timestamp_ms)`

### Requirement: 时间范围判断

系统 SHALL 提供判断时间是否在指定范围内的函数。

#### Scenario: 判断是否在今天

- **WHEN** 调用 `is_today(timestamp_ms)`
- **AND** 时间戳是今天
- **THEN** 返回 True

#### Scenario: 判断是否在昨天

- **WHEN** 调用 `is_yesterday(timestamp_ms)`
- **AND** 时间戳是昨天
- **THEN** 返回 True

#### Scenario: 判断是否在最近 N 天

- **WHEN** 调用 `is_within_days(timestamp_ms, days=7)`
- **AND** 时间戳在 7 天内
- **THEN** 返回 True

#### Scenario: 跨月份判断

- **WHEN** 时间戳在上个月的最后一天
- **AND** 调用 `is_within_days(timestamp_ms, days=7)`
- **THEN** 正确判断（考虑月份天数不同）

### Requirement: 相对时间描述

系统 SHALL 提供友好的相对时间描述。

#### Scenario: 刚刚

- **WHEN** 时间戳在 1 分钟内
- **THEN** 返回 "刚刚"

#### Scenario: N 分钟前

- **WHEN** 时间戳在 60 分钟内
- **THEN** 返回 "N分钟前"

#### Scenario: N 小时前

- **WHEN** 时间戳在 24 小时内
- **THEN** 返回 "N小时前"

#### Scenario: 昨天

- **WHEN** 时间戳是昨天
- **THEN** 返回 "昨天 HH:MM"

#### Scenario: 具体日期

- **WHEN** 时间戳超过 7 天
- **THEN** 返回 "YYYY-MM-DD HH:MM"

### Requirement: 时区处理

系统 SHALL 提供时区相关的处理函数。

#### Scenario: 获取本地时区

- **WHEN** 调用 `get_local_timezone()`
- **THEN** 返回时区字符串（如 "Asia/Shanghai"）
- **AND** 基于系统配置

#### Scenario: UTC 时间转换

- **WHEN** 调用 `utc_to_local(utc_timestamp_ms)`
- **THEN** 返回本地时间的时间戳
- **AND** 正确处理时区偏移

#### Scenario: 本地时间转 UTC

- **WHEN** 调用 `local_to_utc(local_timestamp_ms)`
- **THEN** 返回 UTC 时间的时间戳

### Requirement: 时间差计算

系统 SHALL 提供计算两个时间点之间差值的函数。

#### Scenario: 计算天数差

- **WHEN** 调用 `days_between(start_ts, end_ts)`
- **THEN** 返回相隔的天数（整数）
- **AND** 跨天按自然日计算

#### Scenario: 计算小时差

- **WHEN** 调用 `hours_between(start_ts, end_ts)`
- **THEN** 返回相隔的小时数（浮点数）

#### Scenario: 计算分钟差

- **WHEN** 调用 `minutes_between(start_ts, end_ts)`
- **THEN** 返回相隔的分钟数（整数）

### Requirement: 时间解析

系统 SHALL 支持解析多种时间字符串格式。

#### Scenario: 解析标准时间字符串

- **WHEN** 调用 `parse_time_string("2024-03-01 12:00:00")`
- **THEN** 返回对应的时间戳
- **AND** 格式为 "YYYY-MM-DD HH:MM:SS"

#### Scenario: 解析 ISO 格式

- **WHEN** 调用 `parse_time_string("2024-03-01T12:00:00Z")`
- **THEN** 返回对应的时间戳
- **AND** 正确处理时区

#### Scenario: 解析失败

- **WHEN** 传入无法解析的字符串
- **THEN** 返回 None
- **AND** 不抛出异常

### Requirement: 时间验证

系统 SHALL 提供验证时间戳有效性的函数。

#### Scenario: 有效时间戳

- **WHEN** 传入合理范围的时间戳（如 2024 年）
- **THEN** `is_valid_timestamp()` 返回 True

#### Scenario: 过早时间戳

- **WHEN** 传入 2000 年之前的时间戳
- **THEN** `is_valid_timestamp()` 返回 False

#### Scenario: 未来时间戳

- **WHEN** 传入超过当前时间 + 1 天的时间戳
- **THEN** `is_valid_timestamp()` 返回 False

#### Scenario: None 或空值

- **WHEN** 传入 None 或空字符串
- **THEN** `is_valid_timestamp()` 返回 False

### Requirement: 定时任务时间计算

系统 SHALL 为定时任务提供便捷的时间计算函数。

#### Scenario: 计算下次执行时间

- **WHEN** 调用 `next_execution_time("09:00")`
- **AND** 当前时间是 08:00
- **THEN** 返回今天 09:00 的时间戳

#### Scenario: 跨天执行时间

- **WHEN** 调用 `next_execution_time("09:00")`
- **AND** 当前时间是 10:00
- **THEN** 返回明天 09:00 的时间戳

#### Scenario: 每周执行时间

- **WHEN** 调用 `next_weekly_execution(weekday=0, hour=9)`
- **THEN** 返回下一个周一 09:00 的时间戳
- **AND** weekday: 0=周一, 6=周日

#### Scenario: 每月执行时间

- **WHEN** 调用 `next_monthly_execution(day=1, hour=2)`
- **THEN** 返回下个月 1 号 02:00 的时间戳

### Requirement: 性能优化

时间工具函数 SHALL 经过性能优化，避免重复计算。

#### Scenario: 缓存时区信息

- **WHEN** 多次调用时区相关函数
- **THEN** 时区信息只获取一次
- **AND** 后续调用使用缓存

#### Scenario: 避免重复创建对象

- **WHEN** 频繁调用时间格式化函数
- **THEN** 重用 datetime 对象
- **AND** 不频繁创建新对象

## REMOVED Requirements

### Requirement: 分散的时间处理代码

**Reason**: 代码重复，格式不一致，维护困难
**Migration**:

- `pin_daily_audit.py._format_ms()` → 调用 `format_timestamp_ms()`
- `long_connection_listener.py` 中的时间计算 → 调用月份计算函数
