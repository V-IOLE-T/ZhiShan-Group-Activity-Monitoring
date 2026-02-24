# 飞书 Bot 架构优化提案

## Why

当前飞书群组活跃度监测 Bot 存在多处代码重复、功能重叠和性能瓶颈问题，影响代码可维护性和系统稳定性。具体问题包括：

1. **代码重复严重**：文件上传逻辑在 3 处实现相同功能，用户名获取逻辑在 4 处独立实现，Pin 处理逻辑在多个文件中重复
2. **功能重叠冲突**：PinMonitor（30秒轮询）和 DailyPinAuditor（每日审计）存在功能重叠，可能导致重复处理和数据不一致
3. **同步阻塞风险**：单聊回复在主事件循环中同步执行，MCP 调用（20秒超时）+ 图片生成可能导致长连接心跳超时和消息堆积
4. **线程安全隐患**：部分模块使用非线程安全的 LRU 缓存，批量更新字典未加锁保护

随着业务复杂度增加，这些技术债务将逐渐累积，增加维护成本和故障风险。

## What Changes

### 功能调整
- **移除 PinMonitor 实时轮询**：禁用 `pin_monitor.py` 的 30 秒轮询功能，仅保留 `pin_daily_audit.py` 的每日 09:00 审计
- **保持单聊同步处理**：单聊回复保持同步模式，直接生成图片并返回，MCP 超时增加到 30 秒并添加重试机制

### 代码重构（优先级：高）
- **提取文件上传服务**：将分散在 `storage.py`、`pin_monitor.py`、`pin_daily_audit.py` 的文件上传逻辑统一到 `utils.py`
- **统一 Pin 处理逻辑**：创建 `PinService` 类，合并 PinMonitor、DailyPinAuditor 的重复代码，删除 pin_weekly_report.py（不需要周报功能）
- **统一用户信息获取**：创建 `UserService` 类，集中管理用户名获取和缓存逻辑

### 代码重构（优先级：中）
- **提取时间格式化工具**：在 `utils.py` 添加 `format_timestamp_ms()` 等通用时间处理函数
- **统一 API 端点管理**：将硬编码的飞书 API 端点提取到 `config.py` 的常量类
- **增强线程安全**：将 `long_connection_listener.py` 的 LRU 缓存替换为 ThreadSafeLRUCache

### 风险缓解
- **批量更新持久化**：为 `pending_updates` 字典添加定期持久化机制，防止进程异常退出时数据丢失
- **图片上传清理机制**：为 DocxStorage 的三步图片上传流程添加失败回滚和清理逻辑
- **限流器状态持久化**：为全局 RateLimiter 添加状态持久化，支持多进程部署场景

## Capabilities

### New Capabilities
- `unified-file-upload`: 统一的文件上传服务，支持飞网 Drive API 的三步上传流程（创建空Block → 上传到Block → batch_update）
- `pin-service`: 统一的 Pin 处理服务，支持 Pin 消息获取、详情解析、附件转存、归档和统计
- `user-service`: 统一的用户信息获取服务，支持用户名缓存、群备注获取和批量查询
- `time-utils`: 时间处理工具集，包括毫秒时间戳格式化、月份计算、时区转换等

### Modified Capabilities
- `message-processing`: 保持单聊回复处理流程（同步模式），增加 MCP 超时和重试机制
- `pin-monitoring`: 修改 Pin 监控方式，从"实时轮询 + 每日审计"改为"仅每日审计"

## Impact

### 受影响的代码文件
**移除的文件**：
- `pin_monitor.py` - Pin 实时监控器（功能合并到 pin_daily_audit.py）
- `pin_weekly_report.py` - Pin 周报生成器（不需要周报功能）

**新增的文件**：
- `services/file_upload_service.py` - 统一文件上传服务
- `services/pin_service.py` - 统一 Pin 处理服务
- `services/user_service.py` - 统一用户信息获取服务

**修改的文件**：
- `long_connection_listener.py` - 替换 LRU 缓存为 ThreadSafeLRUCache
- `pin_daily_audit.py` - 使用新的 PinService，整合原 PinMonitor 功能
- `monthly_archiver.py` - 使用新的 PinService
- `reply_card/processor.py` - 简化为同步处理模式
- `reply_card/mcp_client.py` - 增加超时到 30 秒，添加重试机制
- `utils.py` - 添加时间处理工具函数
- `config.py` - 添加 API 端点常量类
- `storage.py` - 添加图片上传清理机制

**删除的文件**：
- `reply_card/placeholder_generator.py` - 占位图生成器（不再需要）

### API 变更
- **BREAKING**: 移除 PinMonitor 相关的调度配置 `PIN_MONITOR_INTERVAL`

### 依赖关系变化
- **新增内部依赖**：所有模块依赖新的 services 层
- **外部依赖不变**：仍使用 lark-oapi、requests、python-dotenv 等

### 部署影响
- 配置文件 `.env` 需移除 `PIN_MONITOR_INTERVAL` 配置（如存在）
- 需确保服务有文件系统权限（用于持久化数据）

### 风险评估
| 风险 | 等级 | 缓解措施 |
|-----|------|---------|
| 重构引入新 Bug | 🟡 中 | 逐步重构，每步添加单元测试，保留原有代码作为对照 |
| Pin 实时提醒延迟 | 🟡 中 | 用户需适应从"实时提醒"改为"每日汇总" |
| 旧数据兼容性 | 🟢 低 | 不涉及数据结构变更，仅代码重构 |

### 成功标准
- [ ] 所有代码重复已消除，DRY 原则得到贯彻
- [ ] Pin 功能仅通过每日审计运行，无重复处理
- [ ] 所有新增服务有完整的单元测试覆盖
- [ ] 线程安全问题已修复，无数据竞争风险
- [ ] 原有功能无回归，所有测试用例通过
