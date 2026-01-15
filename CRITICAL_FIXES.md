# 🔧 紧急问题修复补丁

本文件包含需要立即修复的关键问题的代码示例。

---

## 1. Token过期处理 (auth.py)

### 修复后的完整代码

```python
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FeishuAuth:
    def __init__(self):
        self.app_id = os.getenv('APP_ID')
        self.app_secret = os.getenv('APP_SECRET')
        self.tenant_access_token = None
        self.token_expire_time = 0
        
        # 验证环境变量
        if not self.app_id or not self.app_secret:
            raise ValueError("❌ APP_ID和APP_SECRET必须在.env文件中配置")
    
    def get_tenant_access_token(self, force_refresh=False):
        """获取tenant_access_token，支持自动刷新"""
        # 检查token是否still有效（提前5分钟刷新）
        if not force_refresh and self.tenant_access_token:
            if datetime.now().timestamp() < self.token_expire_time:
                return self.tenant_access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('code') == 0:
                self.tenant_access_token = data['tenant_access_token']
                # 设置过期时间（API返回的expire字段，默认7200秒，提前5分钟刷新）
                expire_in = data.get('expire', 7200) - 300
                self.token_expire_time = datetime.now().timestamp() + expire_in
                print(f"✅ Token获取成功，有效期至 {datetime.fromtimestamp(self.token_expire_time).strftime('%H:%M:%S')}")
                return self.tenant_access_token
            else:
                raise Exception(f"获取token失败: code={data.get('code')}, msg={data.get('msg')}")
        except requests.exceptions.Timeout:
            raise Exception("获取token超时，请检查网络连接")
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取token请求失败: {e}")
    
    def get_headers(self):
        """获取API请求头，自动刷新token"""
        if not self.tenant_access_token or datetime.now().timestamp() >= self.token_expire_time:
            self.get_tenant_access_token(force_refresh=True)
        
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
```

---

## 2. LRU缓存实现 (long_connection_listener.py)

### 在文件顶部添加

```python
from collections import OrderedDict

class LRUCache:
    """简单的LRU缓存实现"""
    def __init__(self, capacity=500):
        self.cache = OrderedDict()
        self.capacity = capacity
    
    def get(self, key, default=None):
        """获取缓存值"""
        if key in self.cache:
            # 移到最后（最近使用）
            self.cache.move_to_end(key)
            return self.cache[key]
        return default
    
    def set(self, key, value):
        """设置缓存值"""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        # 超出容量时删除最久未使用的项
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
    
    def __contains__(self, key):
        return key in self.cache
    
    def __len__(self):
        return len(self.cache)
```

### 替换原有缓存

```python
# 旧代码:
# user_name_cache = {}
# processed_events = set()

# 新代码:
user_name_cache = LRUCache(capacity=500)  # 最多缓存500个用户名
processed_events = LRUCache(capacity=1000)  # 最多缓存1000个事件ID
```

### 更新 get_cached_nickname 函数

```python
def get_cached_nickname(user_id):
    """获取缓存的昵称，如果不存在则从 API 获取并更新缓存"""
    if not user_id:
        return user_id
        
    cached_name = user_name_cache.get(user_id)
    if cached_name:
        return cached_name
    
    print(f"正在获取用户 {user_id} 的群备注...")
    names = collector.get_user_names([user_id])
    if names:
        for uid, name in names.items():
            user_name_cache.set(uid, name)
    
    return user_name_cache.get(user_id, user_id)
```

### 更新事件去重逻辑

```python
def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理接收消息 v2.0 事件"""
    # 0. 事件去重
    event_id = data.header.event_id
    if event_id in processed_events:
        return
    processed_events.set(event_id, True)  # 使用set而不是add
    
    # 不需要手动清理，LRU会自动清理
    
    # ... 后续逻辑
```

---

## 3. 无限循环保护 (collector.py)

### 修复 get_messages 函数

```python
def get_messages(self, hours=1, max_messages=5000, max_pages=100):
    """获取消息，添加安全限制"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    
    # 计算时间阈值（毫秒）
    time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
    
    all_messages = []
    page_token = None
    page_count = 0
    
    while True:
        page_count += 1
        
        # 保护1: 最大页数限制
        if page_count > max_pages:
            print(f"⚠️ 已达到最大页数限制({max_pages})，停止获取")
            break
        
        # 保护2: 最大消息数限制
        if len(all_messages) >= max_messages:
            print(f"⚠️ 已达到消息数量限制({max_messages})，停止获取")
            break
        
        # 构建请求参数
        params = {
            "container_id_type": "chat",
            "container_id": self.chat_id,
            "page_size": 50
        }
        
        if page_token:
            params['page_token'] = page_token
        
        try:
            response = requests.get(
                url, 
                headers=self.auth.get_headers(),
                params=params,
                timeout=10
            )
            data = response.json()
            
            if data.get('code') != 0:
                print(f"❌ 获取消息失败: {data}")
                break
            
            messages = data.get('data', {}).get('items', [])
            
            # 在代码层面过滤时间范围
            for msg in messages:
                create_time = msg.get('create_time', 0)
                if isinstance(create_time, str):
                    create_time = int(create_time)
                
                # 只保留指定时间范围内的消息
                if create_time >= time_threshold:
                    all_messages.append(msg)
                    # 再次检查消息数限制
                    if len(all_messages) >= max_messages:
                        break
            
            # 如果没有更多消息，停止翻页
            if not data.get('data', {}).get('has_more'):
                break
            
            # 检查最后一条消息是否已经超出时间范围
            if messages:
                last_msg_time = messages[-1].get('create_time', 0)
                if isinstance(last_msg_time, str):
                    last_msg_time = int(last_msg_time)
                if last_msg_time < time_threshold:
                    break
            
            page_token = data.get('data', {}).get('page_token')
            time.sleep(0.1)  # 避免请求过快
            
        except requests.exceptions.Timeout:
            print(f"⚠️ 第{page_count}页请求超时，跳过")
            break
        except Exception as e:
            print(f"❌ 获取消息出错: {e}")
            break
    
    print(f"✅ 采集到 {len(all_messages)} 条消息（共{page_count}页）")
    return all_messages
```

---

## 4. API限流保护

### 添加通用的API请求装饰器

```python
import time
from functools import wraps

class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_calls=20, period=60):
        self.max_calls = max_calls
        self.period = period  # 秒
        self.calls = []
    
    def is_allowed(self):
        """检查是否允许调用"""
        now = time.time()
        # 清理过期的记录
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def wait_if_needed(self):
        """如果超限，等待到可以调用"""
        while not self.is_allowed():
            wait_time = self.period - (time.time() - self.calls[0])
            if wait_time > 0:
                print(f"⚠️ API限流中，等待 {wait_time:.1f}秒...")
                time.sleep(min(wait_time, 1))  # 最多等1秒，然后重新检查

# 创建全局限流器
api_limiter = RateLimiter(max_calls=20, period=60)  # 每分钟最多20次

def with_rate_limit(func):
    """API限流装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper
```

### 使用示例

```python
class BitableStorage:
    @with_rate_limit
    def get_record_by_user_month(self, user_id, month):
        # ... 原有代码
        pass
    
    @with_rate_limit
    def update_or_create_record(self, user_id, user_name, metrics_delta):
        # ... 原有代码
        pass
```

---

## 5. 统一错误处理

### 通用API请求包装器

```python
def api_request_wrapper(method, url, **kwargs):
    """统一的API请求处理"""
    # 设置默认超时
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 10
    
    try:
        response = getattr(requests, method)(url, **kwargs)
        data = response.json()
        
        # 检查API返回码
        if data.get('code') == 0:
            return data
        elif data.get('code') == 99991663:  # API限流
            print(f"⚠️ API限流: {data.get('msg')}")
            time.sleep(60)  # 等待1分钟
            return None
        else:
            print(f"❌ API错误 [{data.get('code')}]: {data.get('msg')}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时: {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return None
    except ValueError as e:  # JSON解析错误
        print(f"❌ 响应解析失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return None
```

### 使用示例

```python
# 替换原有的请求代码
# 旧代码:
# response = requests.post(url, headers=..., json=..., timeout=10)
# data = response.json()

# 新代码:
data = api_request_wrapper('post', url, headers=self.auth.get_headers(), json=payload)
if data:
    # 处理数据
    pass
```

---

## 6. 配置文件化

### 创建 config.py

```python
"""配置文件"""

# 缓存配置
CACHE_USER_NAME_SIZE = 500
CACHE_EVENT_SIZE = 1000

# API限流配置
API_RATE_LIMIT_CALLS = 20  # 每周期最多调用次数
API_RATE_LIMIT_PERIOD = 60  # 周期（秒）

# 消息采集配置
MAX_MESSAGES_PER_FETCH = 5000  # 单次最多获取消息数
MAX_PAGES_PER_FETCH = 100  # 单次最多翻页数

# 活跃度权重配置
ACTIVITY_WEIGHTS = {
    'message_count': 1.0,
    'char_count': 0.01,
    'reply_received': 1.5,
    'mention_received': 1.5,
    'topic_initiated': 1.0,
    'reaction_given': 1.0,
    'reaction_received': 1.0
}

# 话题状态时间阈值（天）
TOPIC_ACTIVE_DAYS = 7  # 活跃阈值
TOPIC_SILENT_DAYS = 30  # 沉默阈值

# Token刷新提前时间（秒）
TOKEN_REFRESH_ADVANCE = 300  # 提前5分钟刷新

# API超时配置
API_TIMEOUT = 10  # 秒
```

### 使用配置

```python
from config import ACTIVITY_WEIGHTS, TOPIC_ACTIVE_DAYS

# 在 storage.py 中
def calculate_score(self, fields):
    score = (
        fields["发言次数"] * ACTIVITY_WEIGHTS['message_count'] +
        fields["发言字数"] * ACTIVITY_WEIGHTS['char_count'] +
        # ...
    )
    return round(score, 2)

# 在 long_connection_listener.py 中
def get_topic_status(last_reply_time_ms):
    # ...
    if days_since_last_reply <= TOPIC_ACTIVE_DAYS:
        return "活跃"
    elif days_since_last_reply <= TOPIC_SILENT_DAYS:
        return "沉默"
    else:
        return "冷却"
```

---

## 7. 安全日志输出

### 创建 logger_utils.py

```python
"""日志工具"""
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('feishu_monitor')

def safe_log_dict(data, sensitive_keys=None):
    """安全地记录字典，过滤敏感字段"""
    if sensitive_keys is None:
        sensitive_keys = ['app_id', 'app_secret', 'tenant_access_token', 'access_token']
    
    if isinstance(data, dict):
        filtered = {}
        for key, value in data.items():
            if key in sensitive_keys:
                filtered[key] = '***'
            elif isinstance(value, dict):
                filtered[key] = safe_log_dict(value, sensitive_keys)
            else:
                filtered[key] = value
        return filtered
    return data

def log_api_call(api_name, success, data=None):
    """记录API调用"""
    if success:
        logger.info(f"✅ API调用成功: {api_name}")
    else:
        safe_data = safe_log_dict(data) if data else None
        logger.error(f"❌ API调用失败: {api_name}, 详情: {safe_data}")
```

### 使用示例

```python
from logger_utils import logger, log_api_call, safe_log_dict

# 替换 print
# 旧代码:
# print(f"获取token失败: {data}")

# 新代码:
logger.error(f"获取token失败: {safe_log_dict(data)}")
log_api_call('get_tenant_access_token', success=False, data=data)
```

---

## 应用这些修复

### 修复顺序建议

1. **第一步**: 修复 `auth.py` (Token过期问题)
2. **第二步**: 创建 `config.py` 并应用
3. **第三步**: 在 `long_connection_listener.py` 中实现LRU缓存
4. **第四步**: 修复 `collector.py` (无限循环保护)
5. **第五步**: 可选 - 实现API限流和统一错误处理

### 测试验证

修复后，建议进行以下测试：

1. **Token刷新测试**: 让程序运行超过2小时，验证Token自动刷新
2. **缓存测试**: 查看内存使用，确认不再无限增长
3. **边界测试**: 测试大量消息场景，确认有正确的限制
4. **错误处理测试**: 模拟网络错误，验证重试机制

---

## 更新时间
2026-01-15
