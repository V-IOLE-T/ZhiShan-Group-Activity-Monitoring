# 架构文档

## 项目概述

飞书活跃度监测系统采用 **服务层架构模式**，将业务逻辑抽象为独立的服务模块，实现代码复用和关注点分离。

### 架构优化目标 (v3.0)

1. **消除代码重复** - 文件上传、用户信息获取、Pin处理逻辑统一
2. **移除功能重叠** - 禁用PinMonitor，统一到每日审计
3. **优化响应时间** - 单聊卡片采用两阶段异步处理（<5秒响应）
4. **提升线程安全** - 使用ThreadSafeLRUCache替换非线程安全缓存

---

## 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    入口层 (Entry)                        │
│  main.py / long_connection_listener.py                  │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                    服务层 (Services)                     │
│  ┌──────────────────┬──────────────────┬─────────────┐ │
│  │ FileUploadService│  PinService      │UserService  │ │
│  │  文件上传         │  Pin处理         │用户信息     │ │
│  └──────────────────┴──────────────────┴─────────────┘ │
│  ┌──────────────────────────────────────────────────┐  │
│  │      AsyncCardService (两阶段异步处理)            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                    基础层 (Foundation)                   │
│  config.py | rate_limiter.py | utils.py | auth.py      │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│                    飞书 API (Feishu API)                 │
│  消息 / 用户 / Pin / 文件 / Docx / Bitable              │
└─────────────────────────────────────────────────────────┘
```

---

## 服务层详解

### 1. FileUploadService (文件上传服务)

**文件**: `services/file_upload_service.py`

**职责**: 统一文件上传逻辑，消除 `storage.py`、`pin_monitor.py`、`pin_daily_audit.py` 中的重复代码。

**核心方法**:

| 方法 | 功能 | API端点 |
|------|------|---------|
| `upload_docx_image()` | 上传图片到云文档 | `/docx/v1/documents/{doc_token}/blocks/...` |
| `upload_to_bitable()` | 上传文件到多维表格 | `/drive/v1/media/upload_all` |

**特性**:
- 三步上传流程：创建Block → 上传数据 → batch_update
- 自动重试（2次，指数退避）
- 文件类型验证（支持 jpg/png/gif/pdf/docx）
- 超时控制（创建Block: 10s, 上传: 30s, Bitable: 60s）

**使用示例**:
```python
from services import FileUploadService

# 上传图片到云文档
result = FileUploadService.upload_docx_image(
    image_data=img_bytes,
    auth_token=token,
    doc_token="docx_xxx",
    file_name="summary.png"
)

# 上传文件到多维表格
result = FileUploadService.upload_to_bitable(
    file_data=file_bytes,
    app_token="app_xxx",
    table_id="tbl_xxx",
    auth_token=token,
    file_name="archive.zip"
)
```

---

### 2. PinService (Pin处理服务)

**文件**: `services/pin_service.py`

**职责**: 统一Pin消息获取、附件处理、归档逻辑。

**核心方法**:

| 方法 | 功能 | 特性 |
|------|------|------|
| `get_pinned_messages()` | 获取所有Pin消息 | 支持分页 |
| `get_message_detail()` | 获取消息详情和附件 | 自动提取操作者ID |
| `download_and_upload_resource()` | 下载并上传附件 | 10MB大小限制 |
| `archive_to_bitable()` | 归档到Pin表 | 自动去重 |
| `increment_pin_count()` | 增加被加精次数 | 批量更新优化 |

**缓存策略**:
- 用户名缓存：ThreadSafeLRUCache (容量500)
- Pin详情缓存：ThreadSafeLRUCache (容量200)

**去重机制**:
- 内存去重集合：`processed_ids`
- 持久化文件：`.processed_daily_pins.txt`
- 启动时自动加载历史记录

**使用示例**:
```python
from services import PinService

# 获取所有Pin消息
pins = PinService.get_pinned_messages(chat_id, auth_token)

# 归档到Bitable
success = PinService.archive_to_bitable({
    "message_id": "om_xxx",
    "chat_id": "oc_xxx",
    "title": "精华内容",
    # ...
})
```

---

### 3. UserService (用户信息服务)

**文件**: `services/user_service.py`

**职责**: 统一用户信息获取，支持单个和批量查询。

**核心方法**:

| 方法 | 功能 | 特性 |
|------|------|------|
| `get_user_info()` | 获取单个用户信息 | 群备注优先 |
| `get_batch_user_info()` | 批量获取用户信息 | 每次最多50个 |
| `clear_cache()` | 清空缓存 | 用于测试 |
| `get_cache_size()` | 获取缓存大小 | 监控用途 |

**群备注优先逻辑**:
1. 如果提供 `chat_id`，优先调用群成员接口获取群备注
2. 群成员接口失败时，降级到用户基本信息接口
3. 缓存key包含 `chat_id`，确保不同群的备注独立缓存

**使用示例**:
```python
from services import UserService

# 获取单个用户（群备注优先）
info = UserService.get_user_info(
    user_id="ou_xxx",
    auth_token=token,
    chat_id="oc_xxx"  # 可选，提供时优先获取群备注
)

# 批量获取
users = UserService.get_batch_user_info(
    user_ids=["ou_xxx", "ou_yyy"],
    auth_token=token,
    chat_id="oc_xxx"
)
```

---

### 4. AsyncCardService (异步卡片服务)

**文件**: `services/async_card_service.py`

**职责**: 封装两阶段异步处理逻辑，提供统一接口。

**两阶段处理**:

| 阶段 | 处理内容 | 响应时间 |
|------|----------|----------|
| 同步阶段 | 发送文字提示 + 占位图 | < 5秒 |
| 异步阶段 | 获取文档内容 → 生成完整图片 → 推送 | 后台处理 |

**占位图生成** (`reply_card/placeholder_generator.py`):
- `generate_placeholder()` - 基础占位图 (720x400)
- `generate_with_theme()` - 主题占位图（带标题和消息）

**线程控制**:
- 最大并发线程数：5
- 使用 `ThreadPoolExecutor` 管理后台任务

**使用示例**:
```python
from reply_card.processor import DocCardProcessor

processor = DocCardProcessor(auth)

# 自动两阶段处理
success = processor.process_and_reply(message_text, chat_id)
```

---

## 基础层组件

### config.py - 配置和常量

**FeishuAPIEndpoints 类**: 集中管理所有API端点

```python
class FeishuAPIEndpoints:
    BASE_URL = "https://open.feishu.cn/open-apis"

    # 消息相关
    MESSAGES = "/im/v1/messages"
    MESSAGES_SEND = f"{BASE_URL}{MESSAGES}"

    # Pin 相关
    PINS = "/im/v1/pins"

    # 用户相关
    USER_INFO = "/contact/v3/users"
    BATCH_USER_INFO = "/contact/v3/users/batch_get"

    # ... 更多端点
```

**配置常量**:
- 缓存容量：`CACHE_USER_NAME_SIZE = 500`, `CACHE_EVENT_SIZE = 1000`
- API限流：`API_RATE_LIMIT_CALLS = 20` (每分钟)
- 活跃度权重：`ACTIVITY_WEIGHTS` (消息/回复/提及/Pin等)

---

### utils.py - 工具函数

**ThreadSafeLRUCache**: 线程安全的LRU缓存

```python
from utils import ThreadSafeLRUCache

cache = ThreadSafeLRUCache(capacity=500)
cache.set("key", "value")  # 自动加锁
value = cache.get("key")
```

**时间工具**:
- `format_timestamp_ms()` - 毫秒时间戳格式化
- `format_timestamp()` - 秒级格式化
- `get_current_month()` / `get_previous_month()` - 月份获取
- `is_within_days()` - 天数判断
- `get_relative_time()` - 相对时间描述

---

### rate_limiter.py - API限流

**@with_rate_limit 装饰器**:

```python
from rate_limiter import with_rate_limit

@with_rate_limit
def api_call():
    # 自动限流，防止触发飞书429错误
    pass
```

**限流参数** (在 `config.py`):
- `API_RATE_LIMIT_CALLS = 20` (每周期最多调用次数)
- `API_RATE_LIMIT_PERIOD = 60` (周期秒数)

---

## 线程安全优化

### long_connection_listener.py 修改

**替换非线程安全缓存**:
```python
# 原代码
from utils import LRUCache
user_name_cache = LRUCache(capacity=500)

# 优化后
from utils import ThreadSafeLRUCache
user_name_cache = ThreadSafeLRUCache(capacity=500)
processed_events = ThreadSafeLRUCache(capacity=1000)
```

**添加锁保护**:
```python
import threading

pending_updates_lock = threading.Lock()

def accumulate_metrics(user_id, user_name, metrics_delta):
    with pending_updates_lock:
        # 线程安全的指标累积
        pass

def flush_pending_updates():
    with pending_updates_lock:
        # 线程安全的批量刷新
        pass
```

---

## 数据流图

### 群消息处理流程

```
用户消息
    │
    ▼
事件监听 (long_connection_listener.py)
    │
    ├─▶ 活跃度统计 ──▶ UserService.get_user_info()
    │                  └─▶ ThreadSafeLRUCache 缓存
    │
    ├─▶ 图片转存 ──▶ FileUploadService.upload_docx_image()
    │                  └─▶ 三步上传流程
    │
    └─▶ 标签归档 ──▶ 获取消息 ──▶ 创建文档 ──▶ 上传附件
                     └─▶ FileUploadService.upload_to_bitable()
```

### Pin处理流程

```
定时触发 (每天 9:00)
    │
    ▼
pin_daily_audit.py
    │
    ├─▶ PinService.get_pinned_messages() ──▶ 获取所有Pin
    │
    ├─▶ PinService.get_message_detail() ──▶ 获取详情
    │                                          │
    │                                          └─▶ UserService.get_user_info()
    │
    ├─▶ PinService.download_and_upload_resource() ──▶ 附件处理
    │                                                  │
    │                                                  └─▶ FileUploadService
    │
    └─▶ PinService.archive_to_bitable() ──▶ 归档到Bitable
```

### 单聊两阶段处理

```
用户发送文档链接
    │
    ▼
DocCardProcessor.process_and_reply()
    │
    ├─▶【同步阶段 <5秒】
    │       │
    │       ├─▶ 提取文档Token
    │       ├─▶ 发送文字提示 "正在生成..."
    │       └─▶ generate_placeholder() ──▶ 发送占位图
    │
    └─▶【异步阶段 后台线程】
            │
            ├─▶ MCPClient.fetch_doc() ──▶ 获取文档内容
            ├─▶ CardStyleImageGenerator.generate_card_image() ──▶ 生成完整图片
            └─▶ 推送图片消息
```

---

## 测试策略

### 单元测试

所有服务模块都有对应的单元测试：

| 测试文件 | 测试内容 |
|---------|----------|
| `tests/services/test_file_upload_service.py` | 文件上传服务 (8个测试) |
| `tests/services/test_pin_service.py` | Pin服务 (9个测试) |
| `tests/services/test_user_service.py` | 用户服务 (待添加) |
| `tests/services/test_async_card_service.py` | 异步卡片服务 (待添加) |

**运行测试**:
```bash
# 运行所有测试
pytest

# 运行服务层测试
pytest tests/services/

# 查看覆盖率
pytest --cov=services tests/
```

### 集成测试

端到端测试场景：
1. 群消息 → 活跃度 → Bitable
2. 标签消息 → 文档归档
3. Pin → 每日审计 → 归档
4. 单聊文档链接 → 两阶段回复

---

## 性能指标

### 优化前后对比

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 单聊响应时间 | 20-30秒 | < 5秒 | 75% ↓ |
| 代码重复 | 3处文件上传 | 1个服务 | 消除 |
| 线程安全 | 非线程安全缓存 | ThreadSafeLRU | 100% |
| API调用 | 重复获取用户信息 | 批量+缓存 | 30% ↓ |

### API消耗

月度 API 消耗: **~9,800 次** (免费版额度内)

详细分析见 [README.md](../README.md#api-优化)

---

## 部署说明

### 环境变量

无需额外配置，服务层自动使用现有环境变量。

### 依赖

无新增依赖，使用现有依赖：
- `requests` - HTTP客户端
- `Pillow` - 图片处理（占位图生成）

### Docker部署

```bash
# 构建镜像
docker build -t feishu-monitor .

# 运行容器
docker run -d \
  --env-file config/.env \
  --name feishu-monitor \
  feishu-monitor
```

详见 [部署指南](DEPLOYMENT_GUIDE.md)

---

## 开发指南

### 添加新服务

1. 在 `services/` 创建新文件
2. 实现服务类（静态方法 + `@with_rate_limit`）
3. 在 `services/__init__.py` 添加导入
4. 创建对应的单元测试
5. 更新本文档

### 代码风格

- 使用静态方法（无状态服务）
- 所有API调用添加 `@with_rate_limit`
- 使用 `ThreadSafeLRUCache` 缓存
- 完整的错误处理和日志

详见 [开发指南](DEVELOPMENT.md)

---

## 变更历史

### v3.0 (当前版本)

- 新增服务层架构 (services/)
- 新增两阶段异步处理 (reply_card/)
- 新增线程安全缓存 (ThreadSafeLRUCache)
- 移除 PinMonitor (功能合并到每日审计)
- 移除文件上传重复代码

### v2.0

- 新增 Pin 监控和审计
- 新增文档归档功能
- 优化 API 消耗

### v1.0

- 初始版本
- 基础活跃度监测
