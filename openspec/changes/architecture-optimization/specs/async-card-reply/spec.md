# 异步卡片回复服务 - 功能规范

## ADDED Requirements

### Requirement: 两阶段处理模式
系统 SHALL 将单聊回复拆分为"同步响应 + 异步补充"两个阶段。

#### Scenario: 同步阶段完成
- **WHEN** 收到单聊消息
- **THEN** 在 5 秒内返回基础响应
- **AND** 基础响应包含：文字回复 + 占位图（或完整图片）
- **AND** 主事件循环不被阻塞

#### Scenario: 异步阶段补充
- **WHEN** 同步响应已发送
- **THEN** 后台线程开始生成完整图片
- **AND** 图片生成完成后主动推送给用户
- **AND** 用户无需额外操作

### Requirement: 同步快速响应
系统 SHALL 在同步阶段快速返回，确保长连接心跳正常。

#### Scenario: 文档链接处理 - 同步响应
- **WHEN** 用户发送飞书文档链接
- **THEN** 同步返回：
  - 文字："正在生成卡片，请稍候..."
  - 占位图：带有"生成中"提示的图片
- **AND** 总耗时 < 5 秒

#### Scenario: 纯文本处理 - 同步响应
- **WHEN** 用户发送纯文本消息
- **THEN** 同步返回：
  - 文字：将文本渲染为图片
  - 或直接返回文字图片
- **AND** 总耗时 < 3 秒

#### Scenario: MCP 调用超时处理
- **WHEN** MCP 调用超过 10 秒未返回
- **THEN** 停止等待
- **AND** 返回降级响应：纯文本卡片
- **AND** 日志输出 "[单聊] ⚠️ MCP 调用超时，使用降级方案"

### Requirement: 异步图片生成
系统 SHALL 在后台线程中异步生成完整图片，不阻塞主流程。

#### Scenario: 后台线程生成
- **WHEN** 同步响应完成后
- **THEN** 启动 daemon 线程
- **AND** 在线程中调用 MCP 获取内容
- **AND** 生成完整卡片图片
- **AND** 上传图片并发送给用户

#### Scenario: 图片生成成功
- **WHEN** 完整图片生成成功
- **THEN** 通过飞书 API 发送图片消息给用户
- **AND** 日志输出 "[单聊] ✅ 完整图片已发送"

#### Scenario: 图片生成失败
- **WHEN** 图片生成失败（MCP 错误、渲染错误等）
- **THEN** 发送文字说明："抱歉，图片生成失败，请稍后重试"
- **AND** 不影响已发送的同步响应
- **AND** 日志输出 "[单聊] ❌ 图片生成失败: {错误原因}"

### Requirement: 占位图设计
系统 SHALL 提供友好的占位图，明确告知用户处理状态。

#### Scenario: 占位图内容
- **WHEN** 生成占位图
- **THEN** 图片包含：
  - 标题："正在生成您的卡片"
  - 副标题："预计需要 10-15 秒"
  - 品牌标识：项目 logo 或名称
  - 加载动画效果（静态图表示）
- **AND** 图片尺寸：720x400 像素

#### Scenario: 占位图样式
- **WHEN** 渲染占位图
- **THEN** 使用清晰易读的字体
- **AND** 背景色柔和（浅灰或白色）
- **AND** 文字颜色深色（深灰或黑色）
- **AND** 包含品牌色点缀

### Requirement: 超时和重试策略
系统 SHALL 为异步阶段设置合理的超时和重试策略。

#### Scenario: MCP 调用超时
- **WHEN** MCP 调用超过 10 秒无响应
- **THEN** 取消调用
- **AND** 发送降级响应（纯文本卡片）
- **AND** 不重试

#### Scenario: 图片上传超时
- **WHEN** 图片上传超过 10 秒未完成
- **THEN** 放弃上传
- **AND** 发送文字说明："图片上传失败，请重试"
- **AND** 不重试

#### Scenario: 网络错误重试
- **WHEN** MCP 调用因网络错误失败
- **THEN** 重试 1 次
- **AND** 重试失败则降级

### Requirement: 降级策略
系统 SHALL 在各种异常情况下提供降级方案，确保用户始终收到响应。

#### Scenario: MCP 服务不可用
- **WHEN** MCP 服务（mcp.feishu.cn）无法访问
- **THEN** 降级为纯文本卡片
- **AND** 卡片内容：文档标题 + "请点击链接查看"
- **AND** 日志输出 "[单聊] ⚠️ MCP 服务不可用，使用降级方案"

#### Scenario: 字体文件缺失
- **WHEN** 渲染图片所需字体文件不存在
- **THEN** 使用系统默认字体
- **AND** 日志输出 "[单聊] ⚠️ 字体缺失，使用默认字体"
- **AND** 图片可能不够美观但功能正常

#### Scenario: 资源文件缺失
- **WHEN** 品牌图片等资源文件不存在
- **THEN** 生成不带品牌元素的占位图
- **AND** 功能不受影响

### Requirement: 线程资源管理
系统 SHALL 合理管理后台线程资源，避免资源泄漏。

#### Scenario: Daemon 线程
- **WHEN** 创建后台图片生成线程
- **THEN** 设置 daemon=True
- **AND** 主程序退出时自动清理
- **AND** 不阻塞程序关闭

#### Scenario: 线程并发限制
- **WHEN** 同时有多个单聊请求
- **THEN** 限制最多 5 个并发线程
- **AND** 超过限制时排队等待
- **AND** 日志输出 "[单聊] ⚠️ 线程池已满，请稍候"

#### Scenario: 线程异常捕获
- **WHEN** 后台线程抛出未捕获异常
- **THEN** 异常被捕获并记录
- **AND** 不影响主线程运行
- **AND** 日志输出完整异常堆栈

### Requirement: 用户感知优化
系统 SHALL 通过设计让用户感知良好。

#### Scenario: 响应时间提示
- **WHEN** 用户发送文档链接
- **THEN** 同步响应明确说明预计等待时间
- **AND** 异步补充完成后不重复发送提示

#### Scenario: 处理进度反馈（可选）
- **WHEN** 图片生成时间较长（> 10秒）
- **THEN** 可选：发送中间进度更新
- **AND** 如："正在分析文档（50%）"

#### Scenario: 完成通知
- **WHEN** 完整图片生成并发送成功
- **THEN** 可选：发送简洁的完成提示
- **AND** 避免过度打扰用户

### Requirement: 文档链接识别
系统 SHALL 支持识别多种飞书文档链接格式。

#### Scenario: Docx 文档链接
- **WHEN** 用户发送 `https://xxx.feishu.cn/docx/xxxxx`
- **THEN** 识别为 Docx 文档
- **AND** 提取 docx Token

#### Scenario: Wiki 文档链接
- **WHEN** 用户发送 `https://xxx.feishu.cn/wiki/xxxxx`
- **THEN** 识别为 Wiki 文档
- **AND** 提取 wiki Token

#### Scenario: 短链接
- **WHEN** 用户发送 `https://xxx.feishu.cn/s/xxxxx`
- **THEN** 尝试解析短链接
- **AND** 失败时提示用户发送完整链接

#### Scenario: 非文档链接
- **WHEN** 用户发送其他类型的链接
- **THEN** 返回提示："请发送飞书文档链接"
- **AND** 不尝试处理

### Requirement: 纯文本图片生成
系统 SHALL 支持将纯文本消息渲染为图片。

#### Scenario: 短文本渲染
- **WHEN** 文本长度 < 100 字符
- **THEN** 渲染为单行图片
- **AND** 字体大小适中，清晰可读

#### Scenario: 长文本渲染
- **WHEN** 文本长度 > 100 字符
- **THEN** 自动换行或多行渲染
- **AND** 限制图片高度不超过 800 像素

#### Scenario: 空白消息
- **WHEN** 用户发送空白消息或只有空格
- **THEN** 返回提示："请输入有效内容"
- **AND** 不生成图片

## REMOVED Requirements

### Requirement: 同步阻塞式单聊处理
**Reason**: MCP 调用（20秒）+ 图片生成可能导致长连接心跳超时和消息堆积
**Migration**:
- 拆分 `reply_card/processor.py` 的 `process_and_reply()` 为两阶段
- 添加 `generate_placeholder()` 方法
- 后台线程调用完整图片生成
- MCP 超时从 20 秒缩短为 10 秒
