"""
API速率限制器

防止API调用过快导致被飞书限流（HTTP 429错误）
使用滑动窗口算法实现速率限制
"""
import time
from functools import wraps
from typing import Callable, Dict, Any, List
from config import API_RATE_LIMIT_CALLS, API_RATE_LIMIT_PERIOD


class RateLimiter:
    """
    速率限制器 - 滑动窗口算法

    限制指定时间窗口内的最大调用次数，防止API被限流

    Attributes:
        max_calls: 时间窗口内最大调用次数
        period: 时间窗口长度（秒）
        calls: 调用时间戳列表

    Example:
        >>> limiter = RateLimiter(max_calls=20, period=60)
        >>> limiter.wait_if_needed()  # 如果超限会等待
        >>> # 执行API调用
    """

    def __init__(self, max_calls: int = 20, period: int = 60) -> None:
        """
        初始化速率限制器

        Args:
            max_calls: 周期内最多调用次数，默认20次
            period: 周期长度（秒），默认60秒

        Example:
            >>> # 每分钟最多20次
            >>> limiter = RateLimiter(max_calls=20, period=60)
        """
        self.max_calls: int = max_calls
        self.period: int = period
        self.calls: List[float] = []

    def is_allowed(self) -> bool:
        """
        检查当前是否允许调用

        清理过期的调用记录，检查是否超过限制

        Returns:
            True表示允许调用，False表示已达到限制

        Example:
            >>> limiter = RateLimiter()
            >>> if limiter.is_allowed():
            ...     # 执行API调用
            ...     pass
        """
        now = time.time()
        # 清理过期的记录
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def wait_if_needed(self) -> None:
        """
        如果超限则等待，直到可以调用

        阻塞当前线程直到速率限制允许调用
        显示友好的等待提示信息

        Example:
            >>> limiter = RateLimiter()
            >>> limiter.wait_if_needed()  # 可能会等待几秒
            >>> # 现在可以安全调用API了
        """
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
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取当前限流状态

        返回当前使用情况、剩余额度等信息

        Returns:
            包含以下键的字典:
            - used: 当前周期内已使用的次数
            - remaining: 剩余可用次数
            - limit: 总限制次数
            - period: 周期长度（秒）

        Example:
            >>> limiter = RateLimiter()
            >>> status = limiter.get_status()
            >>> print(f"已使用: {status['used']}/{status['limit']}")
        """
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


def with_rate_limit(func: Callable) -> Callable:
    """
    API限流装饰器

    自动为API调用添加速率限制保护，防止被限流
    使用全局api_limiter实例，所有装饰的函数共享同一限流器

    Args:
        func: 要装饰的函数

    Returns:
        装饰后的函数

    Example:
        >>> @with_rate_limit
        ... def call_feishu_api():
        ...     response = requests.get(url, headers=headers)
        ...     return response.json()
        >>>
        >>> # 自动限流，不会超过配置的速率
        >>> result = call_feishu_api()

    Note:
        - 所有使用此装饰器的函数共享同一个限流器
        - 限流参数从config.py读取
        - 如果超限会自动等待
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        api_limiter.wait_if_needed()
        return func(*args, **kwargs)
    return wrapper
