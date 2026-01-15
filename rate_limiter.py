"""
API速率限制器
防止API调用过快导致被飞书限流
"""
import time
from functools import wraps
from config import API_RATE_LIMIT_CALLS, API_RATE_LIMIT_PERIOD


class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_calls=20, period=60):
        """
        初始化速率限制器
        
        Args:
            max_calls: 周期内最多调用次数
            period: 周期长度（秒）
        """
        self.max_calls = max_calls
        self.period = period
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
            now = time.time()
            # 计算需要等待的时间
            if self.calls:
                wait_time = self.period - (now - self.calls[0])
                if wait_time > 0:
                    # 显示友好提示
                    mins = int(wait_time // 60)
                    secs = int(wait_time % 60)
                    if mins > 0:
                        print(f"⚠️ API限流中，等待 {mins}分{secs}秒...")
                    else:
                        print(f"⚠️ API限流中，等待 {secs}秒...")
                    time.sleep(min(wait_time, 1))  # 最多等1秒，然后重新检查
                else:
                    break
            else:
                break
    
    def get_status(self):
        """获取当前限流状态"""
        now = time.time()
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
        remaining = self.max_calls - len(self.calls)
        return {
            'used': len(self.calls),
            'remaining': remaining,
            'limit': self.max_calls,
            'period': self.period
        }


# 创建全局限流器（每分钟最多20次调用）
api_limiter = RateLimiter(max_calls=API_RATE_LIMIT_CALLS, period=API_RATE_LIMIT_PERIOD)


def with_rate_limit(func):
    """
    API限流装饰器
    
    用法:
        @with_rate_limit
        def some_api_call():
            # API调用代码
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper
