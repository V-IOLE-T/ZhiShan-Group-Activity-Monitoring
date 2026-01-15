"""配置文件 - 统一管理所有配置参数"""

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
ACTIVITY_WEIGHTS = {
    'message_count': 1.0,      # 发言次数权重
    'char_count': 0.01,        # 发言字数权重
    'reply_received': 1.5,     # 被回复数权重
    'mention_received': 1.5,   # 被@次数权重
    'topic_initiated': 1.0,    # 发起话题数权重
    'reaction_given': 1.0,     # 点赞数权重
    'reaction_received': 1.0   # 被点赞数权重
}

# ========== 话题状态时间阈值（天）==========
TOPIC_ACTIVE_DAYS = 7   # 活跃阈值：7天内有回复
TOPIC_SILENT_DAYS = 30  # 沉默阈值：30天内有回复

# ========== Token配置 ==========
TOKEN_REFRESH_ADVANCE = 300  # Token刷新提前时间（秒），提前5分钟刷新

# ========== API超时配置 ==========
API_TIMEOUT = 10  # API请求超时时间（秒）

# ========== 分页延迟配置 ==========
PAGE_SLEEP_TIME = 0.1  # 翻页间隔时间（秒），避免请求过快
