# 用户信息获取服务 - 功能规范

## ADDED Requirements

### Requirement: 统一的用户信息获取接口

UserService SHALL 提供统一的用户信息获取接口，封装飞书 API 调用和缓存逻辑。

#### Scenario: 获取单个用户信息

- **WHEN** 调用 `UserService.get_user_info(user_id, chat_id)`
- **THEN** 返回用户信息字典，包含：
  - `user_id`: 用户 ID
  - `name`: 用户昵称
  - `remark`: 群备注（如果存在）
  - `display_name`: 显示名称（优先群备注，其次昵称）

#### Scenario: 缓存命中

- **WHEN** 用户信息已在缓存中（ThreadSafeLRUCache，容量500）
- **THEN** 直接返回缓存数据
- **AND** 不调用飞书 API
- **AND** 响应时间 < 10ms

#### Scenario: 缓存未命中

- **WHEN** 用户信息不在缓存中
- **THEN** 调用飞书 API 获取用户信息
- **AND** 将结果写入缓存
- **AND** 返回用户信息

#### Scenario: API 调用失败

- **WHEN** 飞书 API 返回错误（用户不存在、网络错误等）
- **THEN** 返回包含默认值的字典：
  - `user_id`: 传入的 user_id
  - `name`: "未知用户"
  - `display_name`: "未知用户"

### Requirement: 批量用户信息获取

UserService SHALL 支持批量获取用户信息，减少 API 调用次数。

#### Scenario: 批量获取成功

- **WHEN** 调用 `UserService.get_batch_user_info(user_ids, chat_id)` 传入多个 user_id
- **THEN** 返回字典，key 为 user_id，value 为用户信息
- **AND** 优先从缓存获取
- **AND** 仅对缓存未命中的用户调用 API

#### Scenario: 部分用户获取失败

- **WHEN** 批量获取中部分用户 API 调用失败
- **THEN** 失败的用户使用默认值
- **AND** 不影响其他用户的数据
- **AND** 返回完整的字典（所有 user_id 都有值）

#### Scenario: 空列表输入

- **WHEN** 传入空的 user_ids 列表
- **THEN** 返回空字典
- **AND** 不调用 API

### Requirement: 群备注优先

UserService SHALL 在获取显示名称时，优先返回群备注，其次返回用户昵称。

#### Scenario: 有群备注

- **WHEN** 用户在群中有自定义备注
- **THEN** `display_name` 返回群备注
- **AND** `remark` 字段包含群备注内容

#### Scenario: 无群备注

- **WHEN** 用户在群中无自定义备注
- **THEN** `display_name` 返回用户昵称
- **AND** `remark` 字段为空字符串

#### Scenario: 用户昵称为空

- **WHEN** 用户既无群备注也无昵称
- **THEN** `display_name` 返回 user_id
- **AND** 日志输出警告信息

### Requirement: 用户名缓存管理

UserService SHALL 使用线程安全的 LRU 缓存，支持缓存更新和失效。

#### Scenario: 缓存自动淘汰

- **WHEN** 缓存达到容量上限（500条）
- **THEN** 自动淘汰最久未使用的条目
- **AND** 新数据成功写入

#### Scenario: 缓存命中统计

- **WHEN** 系统运行期间
- **THEN** 记录缓存命中率
- **AND** 定期输出统计信息到日志

#### Scenario: 主动刷新缓存

- **WHEN** 调用 `UserService.refresh_user_info(user_id)`
- **THEN** 强制从 API 重新获取该用户信息
- **AND** 更新缓存
- **AND** 返回最新数据

### Requirement: 多线程安全

UserService SHALL 确保在多线程环境下的数据一致性。

#### Scenario: 并发读取

- **WHEN** 多个线程同时读取同一用户信息
- **THEN** 所有线程获得一致的数据
- **AND** 不抛出并发异常

#### Scenario: 并发写入

- **WHEN** 多个线程同时写入不同用户信息
- **THEN** 所有写入都成功
- **AND** 缓存数据一致

#### Scenario: 读写并发

- **WHEN** 一个线程读取，另一个线程写入同一用户
- **THEN** 读取线程获得旧数据或新数据（不确定）
- **AND** 不抛出异常
- **AND** 数据最终一致

### Requirement: 用户信息变化监听

UserService SHALL 支持检测用户昵称或群备注的变化。

#### Scenario: 检测到用户改名

- **WHEN** 从 API 获取的用户昵称与缓存不同
- **THEN** 更新缓存
- **AND** 日志输出 "[用户] 用户昵称已更新: 旧名称 → 新名称"

#### Scenario: 检测到群备注变化

- **WHEN** 从 API 获取的群备注与缓存不同
- **THEN** 更新缓存
- **AND** 日志输出 "[用户] 群备注已更新"

#### Scenario: 定期全量刷新

- **WHEN** 系统运行超过 24 小时
- **THEN** 后台线程逐步刷新缓存中的用户信息
- **AND** 避免一次性刷新导致 API 限流

### Requirement: 用户 ID 格式兼容

UserService SHALL 兼容多种用户 ID 格式（open_id、user_id、union_id）。

#### Scenario: 字符串格式 user_id

- **WHEN** 传入字符串格式的 user_id（如 "ou_xxx"）
- **THEN** 正确解析并获取用户信息

#### Scenario: 字典格式 user_id

- **WHEN** 传入字典格式的 user_id（如 `{"open_id": "ou_xxx"}`）
- **THEN** 自动提取 open_id 字段
- **AND** 获取用户信息

#### Scenario: union_id 格式

- **WHEN** 传入 union_id 格式的用户 ID
- **THEN** 尝试使用 union_id 获取用户信息
- **AND** 失败时降级到 open_id

### Requirement: 错误处理和降级

UserService SHALL 在各种错误场景下优雅降级，不影响主流程。

#### Scenario: 网络超时

- **WHEN** API 调用超过 10 秒无响应
- **THEN** 返回默认用户信息（"未知用户"）
- **AND** 不抛出异常
- **AND** 日志输出 "[用户] ⚠️ 获取用户信息超时"

#### Scenario: API 限流

- **WHEN** 触发 API 速率限制
- **THEN** 等待限流解除
- **AND** 自动重试
- **AND** 重试失败则返回默认值

#### Scenario: 用户已退出群组

- **WHEN** 用户已退出被监控的群组
- **THEN** 返回默认用户信息
- **AND** 标记该用户为"已退出"

### Requirement: 性能优化

UserService SHALL 通过多种方式优化性能。

#### Scenario: 批量 API 调用

- **WHEN** 需要获取多个用户信息
- **THEN** 使用批量 API 而非循环调用单个 API
- **AND** 减少网络往返次数

#### Scenario: 预加载热点用户

- **WHEN** 系统启动时
- **THEN** 预加载活跃度排名前 20 的用户信息
- **AND** 这些用户的查询始终命中缓存

#### Scenario: 内存占用控制

- **WHEN** 缓存接近容量上限
- **THEN** 优先淘汰不活跃用户的信息
- **AND** 保留热点用户数据

## Property-Based Testing Properties

### [COMMUTATIVITY] Batch User Info Retrieval
**Property**: Order of `user_ids` does not affect returned data
- **FALSIFICATION STRATEGY**: Randomly shuffle user ID list:
  - `get_batch_user_info([id1, id2, id3])` == `get_batch_user_info([id3, id1, id2])`
  - All users present in result dict
  - Cache misses minimized via single batch API call

### [IDEMPOTENCY] Cache Refresh
**Property**: Refreshing same user info updates cache atomically
- **FALSIFICATION STRATEGY**: Concurrent refreshes for same user:
  - Thread 1: starts refresh, gets old data
  - Thread 2: starts refresh, gets new data
  - Final cache state: consistent (no torn reads)
  - Both threads complete without exception

### [INVARIANT] Display Name Priority
**Property**: `display_name` always follows priority: remark > nickname > user_id
- **FALSIFICATION STRATEGY**: Users with varying attribute states:
  - User with remark: returns remark
  - User without remark but with nickname: returns nickname
  - User with neither: returns user_id
  - Never returns empty string or None

### [BOUNDS] Cache Capacity Constraint
**Property**: Cache never exceeds 500 entries
- **FALSIFICATION STRATEGY**: Insert 501 unique users sequentially:
  - First 500: all cached
  - 501st user: evicts least-recently-used entry
  - Cache size always ≤ 500
  - Evicted users require API re-fetch

## REMOVED Requirements

### Requirement: 分散的用户名获取逻辑

**Reason**: 代码重复，逻辑不一致，缓存策略混乱
**Migration**:

- `long_connection_listener.py.get_cached_nickname()` → 调用 `UserService.get_user_info()`
- `pin_monitor.py.get_user_name()` → 调用 `UserService.get_user_info()`
- `pin_daily_audit.py._get_user_name()` → 调用 `UserService.get_user_info()`
- 统一使用 ThreadSafeLRUCache，替换非线程安全的 LRU 缓存
