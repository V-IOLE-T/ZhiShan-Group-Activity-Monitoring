"""
配置文件 - 统一管理所有配置参数

本模块集中管理项目的所有配置常量，包括：
- 缓存配置
- API限流配置
- 消息采集配置
- 活跃度权重配置
- 话题状态时间阈值
- Token配置
- API超时配置

修改配置后会影响整个应用，建议在开发环境测试后再应用到生产环境
"""

from typing import Dict

# ========== 缓存配置 ==========
CACHE_USER_NAME_SIZE = 500  # 用户名缓存容量
CACHE_EVENT_SIZE = 1000  # 事件去重缓存容量

# ========== API限流配置 ==========
# 飞书API有速率限制，过快调用会被限流（HTTP 429错误）
# 建议设置为每分钟20次以下，留有余量
API_RATE_LIMIT_CALLS = 20  # 每周期最多调用次数
API_RATE_LIMIT_PERIOD = 60  # 周期（秒）
# 示例：20次/60秒 = 平均每3秒最多1次API调用

# ========== 消息采集配置 ==========
MAX_MESSAGES_PER_FETCH = 5000  # 单次最多获取消息数
MAX_PAGES_PER_FETCH = 100  # 单次最多翻页数

# ========== 活跃度权重配置 ==========
# 用于计算活跃度分数的各项指标权重
# 公式: score = message_count * 1.0 + char_count * 0.01 + reply_received * 1.5 + ...
ACTIVITY_WEIGHTS: Dict[str, float] = {
    "message_count": 1.0,  # 发言次数权重
    "char_count": 0.01,  # 发言字数权重（避免刷屏，权重较小）
    "reply_received": 1.5,  # 被回复数权重（内容质量高）
    "mention_received": 1.5,  # 被@次数权重（有影响力）
    "topic_initiated": 1.0,  # 发起话题数权重
    "reaction_given": 1.0,  # 点赞数权重
    "reaction_received": 1.0,  # 被点赞数权重
    "pin_received": 5.0,  # 被Pin次数权重（高价值内容）
}

# ========== 话题状态时间阈值（天）==========
TOPIC_ACTIVE_DAYS = 7  # 活跃阈值：7天内有回复
TOPIC_SILENT_DAYS = 30  # 沉默阈值：30天内有回复

# ========== Token配置 ==========
TOKEN_REFRESH_ADVANCE = 300  # Token刷新提前时间（秒），提前5分钟刷新

# ========== API超时配置 ==========
API_TIMEOUT = 10  # API请求超时时间（秒）

# ========== 分页延迟配置 ==========
PAGE_SLEEP_TIME = 0.1  # 翻页间隔时间（秒），避免请求过快


# ========== API端点常量 ==========
class FeishuAPIEndpoints:
    """
    飞书 API 端点常量

    集中管理所有飞书 API 的 URL 端点，避免硬编码
    使用格式：BASE_URL + 具体路径
    """
    BASE_URL = "https://open.feishu.cn/open-apis"

    # 认证相关
    AUTH = "/auth/v3/tenant_access_token/internal"

    # 消息相关
    MESSAGES = "/im/v1/messages"
    MESSAGES_SEND = f"{BASE_URL}{MESSAGES}"
    MESSAGE_GET = f"{BASE_URL}{MESSAGES}/{{message_id}}"

    # Pin 相关
    PINS = "/im/v1/pins"
    PINS_URL = f"{BASE_URL}{PINS}"

    # 用户相关
    USER_INFO = "/contact/v3/users"
    USER_INFO_URL = f"{BASE_URL}{USER_INFO}/{{user_id}}"
    BATCH_USER_INFO = "/contact/v3/users/batch_get"
    BATCH_USER_INFO_URL = f"{BASE_URL}{BATCH_USER_INFO}"

    # 群组相关
    CHAT_MEMBERS = "/im/v1/chats/{{chat_id}}/members"
    CHAT_MEMBERS_URL = f"{BASE_URL}{CHAT_MEMBERS}"

    # 文件/资源相关
    IMAGES = "/im/v1/images"
    IMAGES_UPLOAD = f"{BASE_URL}{IMAGES}"
    RESOURCES = "/im/v1/resources/{{resource_key}}"
    FILES_DOWNLOAD = "/drive/v1/files/{{file_key}}/download"

    # Drive 相关
    DRIVE_UPLOAD = "/drive/v1/medias/upload_all"
    DRIVE_UPLOAD_URL = f"{BASE_URL}{DRIVE_UPLOAD}"

    # Docx 相关
    DOCX_BLOCKS = "/docx/v1/documents/{{doc_token}}/blocks/{{parent_id}}/children"
    DOCX_BATCH_UPDATE = "/docx/v1/documents/{{doc_token}}/blocks/batch_update"

    # Bitable 相关
    BITABLE_RECORDS = "/bitable/v1/apps/{{app_token}}/tables/{{table_id}}/records"
    BITABLE_RECORDS_SEARCH = f"{BASE_URL}/bitable/v1/apps/{{app_token}}/tables/{{table_id}}/records/search"
