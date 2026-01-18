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
