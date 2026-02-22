# Pin 每日审计功能使用指南

更新时间：2026-02-22

## 功能概览（当前版本）

系统不再使用秒级 Pin 轮询。当前采用每日定时审计：

1. 每天 `09:00` 执行一次任务。
2. 扫描群内当前 Pin 列表。
3. 仅处理“昨天新增且未处理”的 Pin 消息（按 Pin 操作时间判定）。
4. 对每条命中消息执行：
   - 归档 Pin 记录（配置了 `PIN_TABLE_ID` 时）
   - 给发送者增加“被Pin次数”
   - 可选写入精华文档（配置了 `ESSENCE_DOC_TOKEN` 时）
5. 若昨天有新增 Pin，群里发送 1 张“昨日加精”汇总卡片；若无新增则不发卡。

## 执行入口与调度

- 启动入口：`python main.py`
- 调度注册：`pin_scheduler.py`（每天 `09:00`）
- 主进程集成：`long_connection_listener.py`

可手动触发一次审计（测试）：

```python
from pin_scheduler import run_pin_audit_now
run_pin_audit_now()
```

## 配置项

必需配置：

- `CHAT_ID`：目标群 ID
- `BITABLE_APP_TOKEN`：多维表格应用 Token（写表需要）

可选配置：

- `PIN_TABLE_ID`：Pin 归档表 ID；未配置时会跳过归档写表
- `ESSENCE_DOC_TOKEN`：精华文档 Token；配置后会写入精华文档

## 权限要求（飞书应用）

- `im:message.pins:read`：读取群 Pin 列表
- `im:message:readonly`：读取消息详情
- `im:message`：发送“昨日加精”汇总卡片
- `bitable:app`：写入 Pin 归档与活跃度表
- `drive:drive`（若启用附件归档）：上传附件到 Bitable 文件字段

## 去重与统计规则

- 去重文件：`.processed_daily_pins.txt`
- 去重粒度：`message_id`
- 同一条消息只会被成功处理一次
- 取消 Pin 不会回滚“被Pin次数”（当前实现为不扣减）

## 与旧版机制的区别

- 已移除：秒级轮询检测 Pin 变化
- 已移除：按轮询周期即时发送“新加精”卡片
- 已移除：基于“取消 Pin”实时删除归档并扣减统计
- 当前仅保留：每日审计 + 昨日汇总卡片

## 常见问题

### 1. 为什么不是实时提醒？

当前产品策略是每日汇总，降低 API 调用与群内打扰。

### 2. 没收到“昨日加精”卡片怎么办？

先检查：

1. 昨天是否有新加精
2. 调度是否正常运行（09:00 日志）
3. `CHAT_ID` 与消息发送权限是否正确

### 3. 为什么归档没写入？

常见原因：

1. 未配置 `PIN_TABLE_ID`
2. Pin 归档表字段不匹配
3. `bitable:app` 权限未开通或未发布生效
