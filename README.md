# 飞书群聊活跃度监测系统 V4

> **🎉 V4.3 全功能版发布 (2026-01-19)**  
> 新增：单聊智能回复 | Pin消息积分(+5分) | 双重归档 (精华文档 + 数据表格) | 话题深度分析  
> **推荐所有用户立即升级**

基于 Python 开发的**企业级**飞书群聊活跃度监测工具，通过长连接 WebSocket 实时监听群消息和表情回复，自动计算用户活跃度并同步到飞书多维表格，支持 Pin 消息归档和富文本内容保存。

## ✨ 功能特性

### 核心功能
- 🔥 **实时监听**: 基于飞书长连接 WebSocket，毫秒级响应群消息和表情回复事件
- 📊 **7项核心指标**: 发言次数、发言字数、被回复数、被@次数、发起话题数、点赞数、被点赞数
- 🎯 **智能去重**: 自动识别重复事件，避免重复统计（基于 LRU 缓存）
- 🧠 **话题识别**: 支持话题模式群，智能区分话题发起和嵌套回复
- 💾 **按月统计**: 数据按月份自动分组，支持历史数据追溯
- 🔄 **实时同步**: 每条消息即时更新到飞书多维表格
- 📈 **活跃度评分**: 多维度加权计算，科学评估用户活跃度

### 高级功能 ⭐ NEW
- 💬 **单聊智能回复**: 私聊机器人自动生成精美图片回复
  - 文档链接 → 带标题的文档摘要卡片图片
  - 纯文本 → 简洁的内容展示图片
- 📌 **Pin消息归档**: 自动监控群内Pin消息变化，归档重要内容到多维表格
- 🖼️ **富文本保存**: 支持保存图片、文件等附件到Bitable
- 🔗 **消息跳转**: 为每条归档消息生成飞书消息链接，一键跳转查看原文
- 📝 **消息撤回追踪**: 监控消息撤回事件，自动更新统计数据
- 🎨 **互动卡片通知**: Pin消息时自动发送精美卡片提醒到群聊
- ⚡ **API限流保护**: 集成智能限流器，避免触发飞书API速率限制
- 🔒 **线程安全缓存**: 多线程环境下安全的LRU缓存实现

### 生产级特性 🚀 V4.1
- ✅ **环境自动验证**: 启动前自动检查所有必需配置，防止运行时崩溃
- 🏥 **健康检查端点**: 提供HTTP端点实时监控服务状态（支持K8s/Prometheus）
- 🔄 **智能自动重连**: 网络异常时自动重试，最多10次，无需人工干预
- 📋 **日志智能轮转**: 自动管理日志文件大小，防止磁盘空间占满
- 📊 **详细运行统计**: 实时跟踪处理事件数、运行时长等关键指标

## 🏗️ 系统架构

```
飞书群消息/表情回复事件
    ↓
长连接 WebSocket 实时监听
    ↓
事件处理器 (去重 + 解析)
    ↓
指标计算 (7项指标)
    ↓
Bitable 实时更新 (按月累加)
    ↓
活跃度分数自动重算
```

## 📦 项目结构

```
feishu/
# 核心模块
├── auth.py                          # 飞书 API 认证模块 (支持 Token 自动刷新)
├── collector.py                     # 消息采集与用户信息查询
├── calculator.py                    # 活跃度指标计算引擎
├── storage.py                       # Bitable 数据存储模块
├── long_connection_listener.py      # 🚀 实时监听主程序 (推荐)
├── pin_monitor.py                   # 📌 Pin消息监控与归档模块 (NEW)
├── message_renderer.py              # 📄 消息渲染模块 (文档归档)

# 单聊回复模块 (NEW)
├── reply_card/
│   ├── processor.py                 # 💬 单聊消息处理器
│   ├── card_builder.py              # 🎨 卡片构建器
│   ├── card_style_generator.py      # 🖼️ 文档链接卡片图片生成器
│   ├── image_generator.py           # 🖼️ 纯文本图片生成器
│   └── mcp_client.py                # 📡 MCP 客户端 (文档内容获取)

# 工具模块
├── utils.py                         # 工具函数和LRU缓存实现
├── rate_limiter.py                  # API 限流器
├── logger.py                        # 日志管理模块
├── config.py                        # 集中配置管理

# 备用模式
├── main.py                          # 定时任务模式 (备用)
├── webhook_server.py                # Webhook 服务器 (备用)

# 配置与部署
├── requirements.txt                 # 生产环境依赖
├── requirements-dev.txt             # 开发环境依赖
├── .env.example                     # 配置文件模板
├── Dockerfile                       # Docker 镜像构建
├── docker-compose.yml               # Docker Compose 配置
├── .github/workflows/ci.yml         # CI/CD 自动化流程

# 文档
├── README.md                        # 主文档
├── PIN_FEATURE_GUIDE.md             # Pin功能详细指南
├── VISUALIZATION_GUIDE.md           # 数据可视化指南
└── DEVELOPMENT.md                   # 开发者文档
```


## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <your-repo-url>
cd feishu

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 飞书应用配置

#### 2.1 创建应用
1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. 记录 **App ID** 和 **App Secret**

#### 2.2 开通权限
在「开发配置 → 权限管理」中开通以下权限：

**基础权限（必需）**
| 权限名称 | 权限代码 | 用途 |
|---------|---------|------|
| 获取与发送单聊、群组消息 | `im:message` | 读取群消息 |
| 获取群组信息 | `im:chat` | 获取群成员列表 |
| 查看、评论、编辑和管理多维表格 | `bitable:app` | 写入统计数据 |
| 获取用户基本信息 | `contact:user.base:readonly` | 获取用户昵称 |
| 以应用身份读取通讯录 | `contact:contact:readonly_as_app` | 查询用户信息 |

**高级功能权限（推荐）**
| 权限名称 | 权限代码 | 用途 |
|---------|---------|------|
| 获取群组中所有消息 | `im:message:readonly_as_app` | 读取Pin消息详情 |
| 读取、编辑云空间中的文件 | `drive:drive` | 上传附件到云盘 |
| 查看、评论和导出文档 | `docx:document` | 处理文档附件 |
| 查看、评论和导出电子表格 | `sheets:spreadsheet` | 处理表格附件 |

#### 2.3 配置事件订阅
在「开发配置 → 事件订阅」中：
1. 启用「长连接模式」（推荐）
2. 订阅以下事件：
   - `im.message.receive_v1` (接收消息)
   - `im.message.reaction.created_v1` (表情回复)
   - `im.message.message_read_v1` (消息已读，可选)
   - `im.message.recalled_v1` (消息撤回，可选)

#### 2.4 创建多维表格
在飞书中创建多维表格，需要以下两个数据表：

**表1: 用户活跃度统计表**
| 字段名 | 字段类型 | 说明 |
|-------|---------|------|
| 用户ID | 文本 | 用户唯一标识 |
| 用户名称 | 文本 | 群内昵称/备注 |
| 人员 | 人员 | 关联飞书账号 |
| 统计周期 | 文本 | 格式: YYYY-MM |
| 发言次数 | 数字 | 消息发送总数 |
| 发言字数 | 数字 | 文本字符总数 |
| 被回复数 | 数字 | 被他人回复次数 |
| 单独被@次数 | 数字 | 被@提及次数 |
| 发起话题数 | 数字 | 发起新话题次数 |
| 点赞数 | 数字 | 给他人点赞次数 |
| 被点赞数 | 数字 | 收到点赞次数 |
| 被Pin次数 | 数字 | 累计被Pin消息数 |
| 活跃度分数 | 数字 | 综合评分 (保留2位小数) |
| 更新时间 | 数字 | 时间戳 (毫秒) |

**表2: Pin消息归档表（可选，启用Pin监控功能时需要）**
| 字段名 | 字段类型 | 说明 |
|-------|---------|------|
| 消息ID | 文本 | 消息唯一标识 |
| 发送者名称 | 文本 | 消息发送者昵称 |
| 发送者ID | 文本 | 发送者open_id |
| 消息内容 | 文本 | 文本内容 |
| 消息类型 | 单选 | text/image/file等 |
| Pin操作者 | 文本 | 执行Pin的用户昵称 |
| Pin时间 | 文本 | 格式: YYYY-MM-DD HH:MM:SS |
| 消息链接 | URL | 点击跳转到原消息 |
| 附件 | 附件 | 图片、文件等 |

> 💡 详细配置步骤请参考 [PIN_FEATURE_GUIDE.md](PIN_FEATURE_GUIDE.md)

### 3. 配置文件

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 必需配置
APP_ID=cli_xxxxxxxxxx
APP_SECRET=xxxxxxxxxxxxxx
CHAT_ID=oc_xxxxxxxxxx              # 目标群组ID
BITABLE_APP_TOKEN=bascnxxxxxxxxxx  # 多维表格 App Token
BITABLE_TABLE_ID=tblxxxxxxxxxx     # 用户活跃度统计表 ID

# 可选配置（启用Pin监控功能时需要）
PIN_ARCHIVE_TABLE_ID=tblxxxxxxxxxx # Pin消息归档表 ID

# 可选配置（启用消息全量归档时需要）
ARCHIVE_TABLE_ID=tblxxxxxxxxxx     # 消息明细归档表 ID
SUMMARY_TABLE_ID=tblxxxxxxxxxx     # 话题汇总归档表 ID
```

**如何获取这些 ID？**
- **CHAT_ID**: 群设置 → 高级设置 → 群ID
- **BITABLE_APP_TOKEN**: 多维表格 URL 中 `/base/` 后面的部分
- **BITABLE_TABLE_ID**: 活跃度统计表 URL 中 `/tbl` 开头的部分
- **PIN_ARCHIVE_TABLE_ID**: Pin归档表 URL 中 `/tbl` 开头的部分

### 4. 运行程序

#### 方式一：实时监听模式 (推荐)

```bash
# 前台运行
python long_connection_listener.py

# 后台运行 (Windows)
start /B python long_connection_listener.py > activity.log 2>&1

# 后台运行 (Linux/Mac)
nohup python long_connection_listener.py > activity.log 2>&1 &
```

#### 方式二：定时任务模式 (备用)

```bash
# 每小时整点采集一次
python main.py
```

### 5. 生产环境部署（推荐）

如果你没有闲置电脑，推荐使用云服务器 24/7 运行。

#### 方式一：云服务器 + systemd 守护进程

**推荐平台**: 阿里云/腾讯云轻量服务器（约 ¥20-30/月）

```bash
# 1. SSH 登录服务器
ssh root@your_server_ip

# 2. 安装 Python 环境
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

# 3. 克隆项目
git clone <your-repo-url>
cd feishu

# 4. 配置环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. 配置 .env 文件
nano .env  # 填写配置信息

# 6. 创建 systemd 服务
sudo nano /etc/systemd/system/feishu-monitor.service
```

**服务配置文件内容**:
```ini
[Unit]
Description=Feishu Activity Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/feishu
Environment="PATH=/root/feishu/venv/bin"
ExecStart=/root/feishu/venv/bin/python long_connection_listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**启动服务**:
```bash
# 重载配置
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable feishu-monitor

# 启动服务
sudo systemctl start feishu-monitor

# 查看状态
sudo systemctl status feishu-monitor

# 查看实时日志
sudo journalctl -u feishu-monitor -f
```

**常用命令**:
```bash
# 停止服务
sudo systemctl stop feishu-monitor

# 重启服务
sudo systemctl restart feishu-monitor

# 查看最近 100 行日志
sudo journalctl -u feishu-monitor -n 100
```

#### 方式二：Docker 容器化部署

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl start docker
sudo systemctl enable docker

# 2. 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. 上传项目文件到服务器
# 使用 git clone 或 scp 上传

# 4. 配置 .env 文件
nano .env

# 5. 启动容器
docker-compose up -d

# 6. 查看日志
docker-compose logs -f

# 7. 停止容器
docker-compose down
```

**Docker 部署优势**:
- ✅ 环境隔离，不污染系统
- ✅ 一键启动/停止
- ✅ 自动重启
- ✅ 方便迁移

#### 方式三：Railway.app / Render.com (免费额度)

**Railway.app 部署**:
1. 访问 [Railway.app](https://railway.app)
2. 连接 GitHub 仓库
3. 配置环境变量（.env 内容）
4. 自动部署

**注意**: 免费额度有限，超出后按量付费。

## 📊 活跃度计算公式

### 权重配置

```python
活跃度分数 = 发言次数 × 1.0
          + 发言字数 × 0.01
          + 被回复数 × 1.5
          + 单独被@次数 × 1.5
          + 发起话题数 × 1.0
          + 点赞数 × 1.0
          + 被点赞数 × 1.0
          + 被Pin次数 × 5.0
```

### 设计理念

| 指标 | 权重 | 说明 |
|-----|------|------|
| 发言次数 | 1.0 | 基础活跃度 |
| 发言字数 | 0.01 | 鼓励有深度的发言，避免刷屏 |
| 被回复数 | 1.5 | 内容质量高，能引发讨论 |
| 被@次数 | 1.5 | 在群内有影响力 |
| 发起话题数 | 1.0 | 主动发起有价值的讨论 |
| 点赞数 | 1.0 | 积极互动 |
| 被点赞数 | 1.0 | 内容受认可 |
| 被Pin次数 | 5.0 | 高价值内容贡献 (不可回滚) |

## 🔍 核心功能说明

### 1. 智能去重机制
- 使用线程安全的 LRU 缓存避免重复处理事件
- 事件 ID 缓存上限 1000 条，自动淘汰最久未使用的项
- 用户昵称缓存上限 500 条，减少 API 调用

### 2. 话题模式识别
在话题群中，当 `parent_id == root_id` 时：
- 优先使用第一个 @ 对象作为被回复者
- 避免将所有回复都计入话题发起人

### 3. 防重复计分
同一条消息中，如果用户已因"被回复"获得积分，则跳过"被@"积分，避免双重计费。

### 4. 昵称缓存
- 自动缓存群成员昵称，减少 API 调用
- 优先使用群内备注名
- 线程安全，支持并发访问

### 5. 按月统计
- 数据按 `YYYY-MM` 格式分月存储
- 每月自动创建新记录
- 支持跨月数据对比

### 6. Pin消息监控 ⭐ NEW
- 每30秒自动轮询检测群内Pin消息变化
- 自动归档Pin消息的完整内容（文本、图片、文件等）
- 智能下载附件并上传到飞书云盘
- 生成消息跳转链接，一键定位原消息
- 发送精美卡片通知到群聊
- 取消Pin时静默删除归档记录

### 7. API限流保护 ⚡ NEW
- 智能限流器，默认每60秒最多20次API调用
- 自动排队机制，避免触发飞书429错误
- 可在 `config.py` 中自定义限流参数

### 8. 消息撤回追踪 📝 NEW
- 监控消息撤回事件
- 自动从活跃度统计中减去相应数据
- 保持数据准确性

### 9. 单聊智能回复 💬 NEW
- **文档链接识别**: 发送飞书文档链接时，自动生成精美的文档摘要卡片图片
  - 调用 MCP 获取文档内容
  - 生成带绿色标题栏的卡片样式图片
  - 包含文档标题、内容预览、底部引流图片
- **纯文本回复**: 收到普通文本时，生成简洁的内容展示图片
  - 无标题栏设计，更加简洁
  - 支持 Emoji 和多行文本
  - 自动换行和内容截断
- **API 消耗极低**: 每次对话仅消耗 2-3 次 API 调用

## ⚠️ API 用量优化建议

### 当前消耗分析

本系统的 API 调用主要来自两部分：

1. **Pin 消息监控** (后台轮询)
   - 默认每 30 秒轮询一次
   - 月度消耗：**~86,400 次**
   - **占比：80%+**

2. **群消息实时处理**
   - 每条消息约 8-12 次 API 调用
   - 月度消耗：取决于群活跃度

3. **单聊智能回复**
   - 每次对话 2-3 次 API 调用
   - 月度消耗：极低（可忽略）

### 优化方案

如果您遇到 API 限额问题，建议采取以下措施：

#### 方案一：调整 Pin 监控频率（推荐）

编辑 `.env` 文件：
```bash
# 将轮询间隔从 30 秒调整为 5 分钟
PIN_MONITOR_INTERVAL=300
```

**效果**: 月度消耗从 86,400 次降至 8,640 次，**节省 90%**

#### 方案二：禁用 Pin 监控

如果不需要 Pin 功能，可以在 `.env` 中注释掉：
```bash
# PIN_TABLE_ID=tblxxxxxxxxxx
```

**效果**: 完全消除后台轮询消耗

#### 方案三：减少文档归档频率

如果群消息量很大，可以考虑：
- 仅归档包含特定标签的消息
- 禁用 Docx 文档归档功能

### 月度用量估算

| 群活跃度 | Pin 监控 (30s) | Pin 监控 (5min) | 群消息处理 | 总计 (30s) | 总计 (5min) |
|:---|:---|:---|:---|:---|:---|
| 低活跃 (100条/天) | 86,400 | 8,640 | ~30,000 | **~12万** | **~3.5万** |
| 中活跃 (500条/天) | 86,400 | 8,640 | ~150,000 | **~24万** | **~16万** |
| 高活跃 (1000条/天) | 86,400 | 8,640 | ~300,000 | **~39万** | **~31万** |

> 💡 详细分析请参考 [API 用量分析报告](docs/api_usage_report.md)

## 🛠️ 常见问题

### Q1: 如何获取群聊 ID？
**方法一**: 群设置 → 高级设置 → 群ID  
**方法二**: 将应用添加到群后，在事件日志中查看

### Q2: 为什么收不到消息事件？
1. 检查应用是否已添加到目标群组
2. 确认「事件订阅」已启用长连接模式
3. 验证权限 `im:message` 是否已开通
4. 查看终端日志是否有连接成功提示

### Q3: 如何修改权重配置？
编辑以下文件中的计算公式：
- `calculator.py` (第 83-89 行)
- `storage.py` (第 88-97 行、第 129-137 行)

### Q4: 数据不准确怎么办？
1. 检查 `.env` 中的 `CHAT_ID` 是否正确
2. 确认多维表格字段名称与代码一致
3. 查看日志中是否有 API 错误信息

### Q5: Token 过期怎么办？
代码会自动重新获取 `tenant_access_token`，无需手动处理。

### Q6: 如何查看历史消息？
长连接模式只能接收实时消息。如需统计历史数据，使用 `main.py` 的定时任务模式。

### Q7: 能否同时监听多个群？
当前版本仅支持单群监听。如需多群，可运行多个进程，每个配置不同的 `.env` 文件。

### Q8: 如何启用Pin消息监控功能？
1. 在 `.env` 中配置 `PIN_ARCHIVE_TABLE_ID`
2. 在Bitable中创建Pin归档表（参考 [PIN_FEATURE_GUIDE.md](PIN_FEATURE_GUIDE.md)）
3. 确保已开通相关权限（`im:message:readonly_as_app`、`drive:drive`）
4. 运行 `long_connection_listener.py`，Pin监控会自动启动

### Q9: Pin消息的附件无法上传怎么办？
1. 确认已开通 `drive:drive` 权限
2. 检查应用是否已添加到目标群组
3. 查看日志中的具体错误信息
4. 确保附件文件大小在飞书限制范围内（单文件 < 20MB）

### Q10: 如何使用单聊智能回复功能？
直接私聊机器人即可：
- **发送文档链接**: 机器人自动生成文档摘要卡片图片
- **发送纯文本**: 机器人生成简洁的内容展示图片

**注意**: 确保已开通以下权限：
- `im:message` (接收单聊消息)
- `im:message:send_as_bot` (发送消息)
- `drive:drive` (上传图片)

### Q11: 如何调整代码格式和进行开发？
本项目配置了完整的开发环境：
```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 自动格式化代码
black .
isort .

# 代码检查
flake8 .
mypy auth.py collector.py

# 运行测试
pytest tests/
```
详细说明请参考 [DEVELOPMENT.md](DEVELOPMENT.md)

## 📝 日志说明

### 正常日志示例
```
[V3-LOG] [23:35:12] 收到新消息=========================
  > 消息ID: om_xxxxx
  > 父ID (parent_id): om_yyyyy
  > 根ID (root_id): om_zzzzz
实时更新: 张三 (字数: 42)
  > [API] ✅ 找到已存在的记录
  > [API] 正在更新记录 recxxxxxx...
  > [API] ✅ 更新成功
  > [更新] 增加被回复数给: 李四
✅ 实时同步圆满成功
```

### 错误日志处理
- `❌ 更新表格失败`: 检查 Bitable 权限和字段配置
- `⚠️ Bitable 搜索失败`: 确认「统计周期」字段已创建
- `无法获取消息发送者`: 消息可能已被撤回或删除

## 🔐 安全建议

1. **不要提交 `.env` 文件到 Git**
2. 定期更换 `APP_SECRET`
3. 仅授予必要的最小权限
4. 生产环境使用独立的飞书应用

## � 相关文档

- 📌 [Pin功能完整指南](PIN_FEATURE_GUIDE.md) - Pin消息监控与归档功能详解
- 📊 [数据可视化指南](VISUALIZATION_GUIDE.md) - 使用飞书仪表盘展示数据
- 🚀 [快速开始：可视化](VISUALIZATION_QUICKSTART.md) - 5分钟搭建数据看板
- 💻 [开发者文档](DEVELOPMENT.md) - 代码结构、测试、贡献指南
- 🔄 [CI/CD配置指南](CI_CD_GUIDE.md) - 自动化测试与部署

## �📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题，请提交 GitHub Issue。
