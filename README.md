# 飞书群聊活跃度监测系统

基于 Python 开发的飞书群聊活跃度监测工具，自动采集群聊消息并计算用户活跃度指标。

## 功能特性

- ✅ 每小时自动采集群聊消息
- ✅ 计算5项核心指标：发言次数、发言字数、被回复数、被@次数、发起话题数
- ✅ 活跃度Top10排行榜
- ✅ 数据自动写入飞书多维表格
- ✅ 简化的评分模型

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置应用

1. 访问[飞书开放平台](https://open.feishu.cn/)创建自建应用
2. 开通权限：
   - `im:message:read_all` (读取群消息)
   - `im:chat` (获取群信息)
   - `bitable:app` (多维表格读写)
   - `contact:user.base:readonly` (获取用户信息)
3. 获取 App ID 和 App Secret
4. 创建多维表格并配置字段

### 3. 配置文件

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填写真实信息
```

### 4. 运行

```bash
# 立即执行一次
python main.py

# 后台运行（Linux）
nohup python main.py > activity.log 2>&1 &

# 后台运行（Windows）
start /B python main.py > activity.log 2>&1
```

## 多维表格字段

在飞书多维表格中创建以下字段：

| 字段名 | 字段类型 | 说明 |
|-------|---------|------|
| 用户ID | 文本 | 主键 |
| 用户名称 | 文本 | 显示名 |
| 发言次数 | 数字 | - |
| 发言字数 | 数字 | - |
| 被回复数 | 数字 | - |
| 被@次数 | 数字 | - |
| 发起话题数 | 数字 | - |
| 活跃度分数 | 数字 | 保留2位小数 |
| 更新时间 | 日期 | 格式:YYYY-MM-DD HH:mm:ss |

## 项目结构

```
feishu/
├── auth.py           # 认证模块
├── collector.py      # 消息采集模块
├── calculator.py     # 指标计算模块
├── storage.py        # 数据写入模块
├── main.py           # 主程序
├── requirements.txt  # 依赖清单
├── .env.example      # 配置模板
└── .gitignore        # Git忽略文件
```

## 常见问题

### Q1: 如何获取群聊ID？
在群设置->高级设置->群ID中复制，或将应用添加到群后通过机器人事件获取。

### Q2: 为什么看不到历史消息？
需要先将应用添加到群聊，之后才能读取新消息。历史消息权限需要在飞书开放平台->事件订阅中单独配置。

### Q3: Token过期怎么办？
代码会自动重新获取 token。如果频繁失败，请检查 App ID 和 Secret 是否正确。

## 许可证

MIT License
