# 云服务器部署后文档卡片不显示内容 - 诊断指南

## 问题描述

部署到云服务器后，发送飞书文档链接时，卡片不显示文档内容，只显示文档链接。

从日志看到：
```
> [单聊] 提取的文本内容: https://xcnke0rwjera.feishu.cn/wiki/...
> [MCP] 单聊文档提取已完成
```

但卡片图片中内容为空或只显示链接。

## 可能的原因

### 1. **MCP API 网络访问问题（最可能）**

云服务器可能无法访问飞书 MCP 服务：`https://mcp.feishu.cn/mcp`

**诊断方法：**
- 在云服务器上执行：
  ```bash
  curl -v https://mcp.feishu.cn/mcp
  ```
- 检查是否有防火墙、代理或网络限制

**解决方案：**
- 配置云服务器的出站规则，允许访问 `mcp.feishu.cn`
- 如果有代理，需要在代码中配置 `requests` 的代理设置

### 2. **文档权限问题**

机器人可能没有读取该文档的权限。

**诊断方法：**
- 检查机器人是否被添加为文档的协作者
- 确认应用是否开通了「云文档」权限：
  - 登录飞书开放平台
  - 进入应用 -> 权限管理
  - 确保开通：`docs:doc:readonly`、`wiki:wiki:readonly` 等权限

**解决方案：**
- 将文档分享给机器人或设为全员可见
- 在飞书开放平台开通必要的云文档权限

### 3. **Token 问题**

`tenant_access_token` 在云服务器上可能失效或获取失败。

**诊断方法：**
- 查看完整日志，确认是否有 token 获取失败的错误
- 检查云服务器上的 `.env` 配置是否正确

**解决方案：**
- 确保 `APP_ID` 和 `APP_SECRET` 配置正确
- 检查应用是否在飞书开放平台启用

### 4. **时间同步问题**

云服务器时间不准确可能导致 token 验证失败。

**诊断方法：**
```bash
date
```

**解决方案：**
```bash
# Linux
sudo ntpdate time.windows.com

# 或安装 NTP 服务
sudo apt-get install ntp
sudo systemctl start ntp
```

## 已增强的日志

我已经为你添加了详细的调试日志，重新部署后，你会看到：

### MCP 调用日志：
```
🚀 调用 MCP 工具: fetch-doc, 参数: {'docID': 'xxx'}
🌐 请求URL: https://mcp.feishu.cn/mcp
🔑 使用Token前缀: t-xxx...
📡 HTTP状态码: 200
📡 响应内容: {...}
✅ MCP 调用成功
```

### 文档解析日志：
```
✅ MCP 成功返回内容，长度: 1234 字符
📄 内容预览: {"title":"文档标题","markdown":"..."}...
📋 解析成功 - 标题: 文档标题
📋 预览内容长度: 500 字符
📋 预览内容: ...
```

## 诊断步骤

1. **重新部署代码到云服务器**（包含新增的日志）

2. **再次发送文档链接**，观察完整日志

3. **根据日志输出判断问题：**

   - 如果看到 `❌ MCP 连接失败` 或 `❌ MCP 请求超时`
     → **网络问题**，检查云服务器网络配置
   
   - 如果看到 `❌ MCP 工具内部错误: 权限不足`
     → **权限问题**，检查机器人和应用权限
   
   - 如果看到 `❌ MCP 返回空内容或调用失败`
     → 查看更详细的错误信息
   
   - 如果看到 `✅ MCP 成功返回内容` 但 `❌ 解析文档信息失败`
     → 返回的数据格式可能有问题，需要检查原始内容

## 快速测试

在云服务器上手动测试 MCP API：

```bash
# 替换下面的 TOKEN 为你的 tenant_access_token
curl -X POST https://mcp.feishu.cn/mcp \
  -H "Content-Type: application/json" \
  -H "X-Lark-MCP-TAT: YOUR_TOKEN" \
  -H "X-Lark-MCP-Allowed-Tools: fetch-doc" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "fetch-doc",
      "arguments": {
        "docID": "YwNEwIU1eiFiKekwNtgcb3kBnJg"
      }
    }
  }'
```

如果返回 `timeout` 或 `connection refused`，说明是网络问题。
如果返回 `permission denied`，说明是权限问题。

## 后续行动

1. **先在云服务器上查看新的详细日志**
2. **根据日志错误信息确定具体原因**
3. **提供完整的日志输出**，我可以帮你进一步分析

## 注意事项

- 日志中可能包含敏感 token，分享时请脱敏（遮盖前后部分）
- 如果使用 Docker 部署，确保容器有网络访问权限
- 检查云服务商是否有特殊的网络安全组配置
