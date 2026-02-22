# 统一文件上传服务 - 功能规范

## ADDED Requirements

### Requirement: 三步图片上传流程

系统 SHALL 实现飞书 Docx 图片上传的标准三步流程：

1. 创建空的图片 Block，获取 block_id
2. 上传图片数据到该 Block
3. 通过 batch_update 将 Block 添加到文档

文件上传服务 SHALL 提供统一的静态方法封装此流程。

#### Scenario: 图片上传成功

- **WHEN** 调用 `FileUploadService.upload_docx_image()` 传入有效图片数据和认证 token
- **THEN** 返回包含 `block_id` 的字典
- **AND** 日志输出 "[Docx] ✅ 图片上传成功: {file_token}"

#### Scenario: 创建 Block 失败

- **WHEN** 第一步创建空 Block 时 API 返回错误
- **THEN** 返回 `None`
- **AND** 日志输出 "[Docx] ❌ 创建图片 Block 失败"
- **AND** 不执行后续上传步骤

#### Scenario: 图片上传失败

- **WHEN** 创建 Block 成功但上传图片数据失败
- **THEN** 返回 `None`
- **AND** 日志输出 "[Docx] ❌ 图片数据上传失败"
- **AND** 空 Block 留在文档中（后续清理机制处理）

#### Scenario: Batch Update 失败

- **WHEN** 图片上传成功但 batch_update 失败
- **THEN** 返回 `None`
- **AND** 日志输出 "[Docx] ❌ 添加图片 Block 到文档失败"
- **AND** 图片已上传但未关联到文档

### Requirement: 文件上传到 Bitable

系统 SHALL 提供将文件上传到飞书多维表格的功能，支持附件类型。

#### Scenario: 附件上传成功

- **WHEN** 调用 `FileUploadService.upload_to_bitable()` 传入文件数据和 app_token
- **THEN** 返回包含 `file_token` 的字典
- **AND** 日志输出 "✅ 文件已上传到 Bitable"

#### Scenario: 附件上传超时

- **WHEN** 文件上传超过 60 秒未完成
- **THEN** 返回 `None`
- **AND** 日志输出 "⚠️ 文件上传超时"

#### Scenario: API 限流

- **WHEN** 触发 API 限流（20次/60秒）
- **THEN** 自动等待直到限流解除
- **AND** 日志输出 "⚠️ API限流中，等待 X秒..."

### Requirement: 速率限制保护

所有文件上传方法 SHALL 使用 `@with_rate_limit` 装饰器保护，遵守飞书 API 速率限制。

#### Scenario: 自动限流等待

- **WHEN** 连续调用文件上传服务超过 20 次/分钟
- **THEN** 后续调用自动等待直到配额恢复
- **AND** 不会触发 HTTP 429 错误

### Requirement: 错误清理机制

系统 SHALL 在图片上传失败时提供清理机制，移除遗留的空 Block。

#### Scenario: 清理空 Block

- **WHEN** 图片上传失败后在文档中留下空 Block
- **THEN** 系统定期扫描并删除无内容的图片 Block
- **AND** 日志输出清理的 Block 数量

### Requirement: 文件类型验证

系统 SHALL 验证上传文件的类型，仅允许支持的格式（图片：jpg/png/gif，文档：pdf/docx）。

#### Scenario: 不支持的文件类型

- **WHEN** 尝试上传不支持的文件类型（如 .exe）
- **THEN** 返回 `None`
- **AND** 日志输出 "❌ 不支持的文件类型: {extension}"

#### Scenario: 图片格式验证

- **WHEN** 上传图片文件但扩展名与实际内容不匹配
- **THEN** 通过文件头（magic bytes）验证真实格式
- **AND** 拒绝格式不符的文件

### Requirement: 超时控制

系统 SHALL 为不同操作设置合理的超时时间：

- 创建 Block: 10 秒
- 上传图片: 30 秒
- 上传到 Bitable: 60 秒
- Batch Update: 10 秒

#### Scenario: 创建 Block 超时

- **WHEN** 创建 Block API 调用超过 10 秒无响应
- **THEN** 抛出超时异常
- **AND** 调用方可捕获并处理

#### Scenario: 图片上传超时

- **WHEN** 图片数据上传超过 30 秒未完成
- **THEN** 取消上传
- **AND** 返回 `None`

### Requirement: 重试策略

系统 SHALL 在网络错误时实施重试策略：

- 创建 Block: 失败后重试 1 次
- 上传图片: 失败后重试 2 次（指数退避）
- Batch Update: 不重试（文档状态可能已变化）

#### Scenario: 网络抖动重试成功

- **WHEN** 创建 Block 因网络错误失败
- **THEN** 自动重试 1 次
- **AND** 重试成功则返回正常结果

#### Scenario: 重试次数用尽

- **WHEN** 图片上传重试 2 次后仍失败
- **THEN** 返回 `None`
- **AND** 日志输出 "❌ 图片上传失败，已重试 2 次"

## REMOVED Requirements

### Requirement: 分散的文件上传实现

**Reason**: 代码重复，维护成本高，Bug 修复需多处同步
**Migration**:

- `storage.py._upload_to_drive()` → 调用 `FileUploadService.upload_docx_image()`
- `pin_monitor.py._upload_to_drive()` → 调用 `FileUploadService.upload_to_bitable()`
- `pin_daily_audit.py._upload_to_drive()` → 调用 `FileUploadService.upload_to_bitable()`
