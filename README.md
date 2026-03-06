# 飞书活跃度监测系统

> **项目文档已移至 `docs/` 目录**

## 📚 快速导航

- [完整文档](docs/README.md) - 详细的项目说明
- [Program 文档](docs/PROGRAM.md) - 运行稳定性与功能全景
- [部署指南](docs/DEPLOYMENT_GUIDE.md) - 如何部署到服务器
- [开发指南](docs/DEVELOPMENT.md) - 开发者文档
- [Pin 功能说明](docs/PIN_FEATURE_GUIDE.md) - Pin 机制说明
- [可视化指南](docs/VISUALIZATION_GUIDE.md) - 数据可视化

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp config/.env.example config/.env

# 编辑配置文件
nano config/.env
```

### 3. 运行程序

**方式一：使用新入口 (推荐)**

```bash
python main.py
```

**方式二：使用原入口 (向后兼容)**

```bash
python long_connection_listener.py
```

## 📁 项目结构

```
feishu/
├── main.py                      # 主入口 (新)
├── long_connection_listener.py  # 原入口 (兼容)
├── docs/                        # 📚 文档
├── config/                      # ⚙️ 配置文件
├── deployment/                  # 🐳 部署相关
├── scripts/                     # 🔧 辅助脚本
├── services/                    # 🔧 服务层 (新增)
│   ├── __init__.py
│   ├── file_upload_service.py   # 文件上传服务
│   ├── pin_service.py           # Pin 处理服务
│   ├── user_service.py          # 用户信息服务
│   └── async_card_service.py    # 异步卡片服务
├── reply_card/                  # 💬 单聊卡片处理
│   ├── placeholder_generator.py # 占位图生成
│   ├── processor.py             # 两阶段处理器
│   └── mcp_client.py            # MCP 客户端
├── tests/                       # 🧪 测试
│   └── services/                # 服务层单元测试
└── *.py                         # 核心代码
```

详见 [架构文档](docs/ARCHITECTURE.md)

## ⚡ 核心功能

- ✅ 实时消息监听和处理
- ✅ 用户活跃度统计 (批量更新优化)
- ✅ 每周 Pin 审计 (每周一 9:00 检查上周新增)
- ✅ 文档归档 (仅归档带标签消息)
- ✅ 点赞统计
- ✅ 单聊智能回复 (两阶段异步处理，<5秒响应)
- ✅ 统一服务层 (文件上传、用户信息、Pin处理)
- ✅ 线程安全优化 (ThreadSafeLRUCache)

## 📊 API 优化

月度 API 消耗: **~9,800 次** (免费版额度内)

详见 [优化说明](docs/README.md#api-优化)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📄 许可

MIT License
