"""
rate_limiter.py 单元测试

测试速率限制器的核心功能和边界情况
"""

import unittest
import time
from unittest.mock import patch
from rate_limiter import RateLimiter, with_rate_limit


class TestRateLimiter(unittest.TestCase):
    """测试RateLimiter类"""

    def test_initialization(self):
        """测试限流器初始化"""
        limiter = RateLimiter(max_calls=10, period=60)

        self.assertEqual(limiter.max_calls, 10)
        self.assertEqual(limiter.period, 60)
        self.assertEqual(len(limiter.calls), 0)

    def test_default_parameters(self):
        """测试默认参数"""
        limiter = RateLimiter()

        self.assertEqual(limiter.max_calls, 20)
        self.assertEqual(limiter.period, 60)

    def test_is_allowed_basic(self):
        """测试基本的限流允许逻辑"""
        limiter = RateLimiter(max_calls=3, period=60)

        # 前3次调用应该被允许
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())

        # 第4次调用应该被拒绝
        self.assertFalse(limiter.is_allowed())
        self.assertFalse(limiter.is_allowed())

    def test_is_allowed_records_time(self):
        """测试is_allowed会记录调用时间"""
        limiter = RateLimiter(max_calls=2, period=60)

        self.assertEqual(len(limiter.calls), 0)

        limiter.is_allowed()
        self.assertEqual(len(limiter.calls), 1)

        limiter.is_allowed()
        self.assertEqual(len(limiter.calls), 2)

        # 第3次被拒绝，不记录
        limiter.is_allowed()
        self.assertEqual(len(limiter.calls), 2)

    def test_sliding_window_cleanup(self):
        """测试滑动窗口会清理过期记录"""
        limiter = RateLimiter(max_calls=2, period=1)  # 1秒窗口

        # 第1、2次调用
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())

        # 第3次被拒绝
        self.assertFalse(limiter.is_allowed())

        # 等待超过窗口期
        time.sleep(1.1)

        # 旧记录被清理，可以再次调用
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())

    def test_get_status_initial(self):
        """测试初始状态"""
        limiter = RateLimiter(max_calls=10, period=60)

        status = limiter.get_status()

        self.assertEqual(status["used"], 0)
        self.assertEqual(status["remaining"], 10)
        self.assertEqual(status["limit"], 10)
        self.assertEqual(status["period"], 60)

    def test_get_status_after_calls(self):
        """测试调用后的状态"""
        limiter = RateLimiter(max_calls=5, period=60)

        limiter.is_allowed()
        limiter.is_allowed()
        limiter.is_allowed()

        status = limiter.get_status()

        self.assertEqual(status["used"], 3)
        self.assertEqual(status["remaining"], 2)
        self.assertEqual(status["limit"], 5)

    def test_get_status_cleans_old_calls(self):
        """测试get_status会清理过期记录"""
        limiter = RateLimiter(max_calls=3, period=1)

        limiter.is_allowed()
        limiter.is_allowed()

        status1 = limiter.get_status()
        self.assertEqual(status1["used"], 2)

        # 等待过期
        time.sleep(1.1)

        status2 = limiter.get_status()
        self.assertEqual(status2["used"], 0)
        self.assertEqual(status2["remaining"], 3)

    def test_wait_if_needed_no_wait(self):
        """测试未超限时不需要等待"""
        limiter = RateLimiter(max_calls=3, period=60)

        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time

        # 应该立即返回，不等待
        self.assertLess(elapsed, 0.1)

    def test_wait_if_needed_with_wait(self):
        """测试超限时会等待"""
        limiter = RateLimiter(max_calls=2, period=2)

        # 用完额度
        limiter.is_allowed()
        limiter.is_allowed()

        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time

        # 应该等待了至少1秒（实际会等2秒，但测试中会重新检查）
        self.assertGreater(elapsed, 0.5)

        # 等待后应该可以调用
        self.assertTrue(limiter.is_allowed())

    def test_multiple_periods(self):
        """测试多个周期的行为"""
        limiter = RateLimiter(max_calls=2, period=1)

        # 第1个周期
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())
        self.assertFalse(limiter.is_allowed())

        time.sleep(1.1)

        # 第2个周期
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())
        self.assertFalse(limiter.is_allowed())

    def test_partial_window_expiry(self):
        """测试部分记录过期的情况"""
        limiter = RateLimiter(max_calls=3, period=2)

        # T=0: 添加2个调用
        limiter.is_allowed()
        limiter.is_allowed()

        time.sleep(1)

        # T=1: 再添加1个调用
        limiter.is_allowed()

        # 现在有3个调用，应该被拒绝
        self.assertFalse(limiter.is_allowed())

        time.sleep(1.1)

        # T=2.1: 前2个调用已过期，应该有2个空位
        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())

        # 第3个空位还被占用，应该被拒绝
        self.assertFalse(limiter.is_allowed())


class TestWithRateLimitDecorator(unittest.TestCase):
    """测试with_rate_limit装饰器"""

    def test_decorator_basic(self):
        """测试装饰器基本功能"""
        call_count = [0]

        @with_rate_limit
        def test_func():
            call_count[0] += 1
            return "success"

        result = test_func()

        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 1)

    def test_decorator_with_args(self):
        """测试装饰器处理带参数的函数"""

        @with_rate_limit
        def add(a, b):
            return a + b

        result = add(2, 3)
        self.assertEqual(result, 5)

    def test_decorator_with_kwargs(self):
        """测试装饰器处理关键字参数"""

        @with_rate_limit
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = greet("Alice", greeting="Hi")
        self.assertEqual(result, "Hi, Alice")

    def test_decorator_preserves_function_name(self):
        """测试装饰器保留函数名"""

        @with_rate_limit
        def my_function():
            """My docstring"""
            pass

        self.assertEqual(my_function.__name__, "my_function")
        self.assertEqual(my_function.__doc__, "My docstring")

    @patch("rate_limiter.api_limiter")
    def test_decorator_calls_wait_if_needed(self, mock_limiter):
        """测试装饰器调用wait_if_needed"""

        @with_rate_limit
        def test_func():
            return "result"

        test_func()

        # 应该调用了wait_if_needed
        mock_limiter.wait_if_needed.assert_called_once()

    def test_decorator_rate_limiting(self):
        """测试装饰器实际限流效果"""
        # 创建一个小的限流器用于测试
        test_limiter = RateLimiter(max_calls=2, period=1)

        call_times = []

        def test_func():
            call_times.append(time.time())
            return "ok"

        # 手动装饰函数
        @with_rate_limit
        def decorated_func():
            # 使用测试限流器而不是全局限流器
            test_limiter.wait_if_needed()
            return test_func()

        # 第1、2次应该立即执行
        decorated_func()
        decorated_func()

        # 第3次应该被限流，需要等待
        start = time.time()
        decorated_func()
        elapsed = time.time() - start

        # 应该等待了接近1秒
        self.assertGreater(elapsed, 0.5)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_zero_max_calls(self):
        """测试最大调用次数为0的情况"""
        limiter = RateLimiter(max_calls=0, period=60)

        # 任何调用都应该被拒绝
        self.assertFalse(limiter.is_allowed())
        self.assertFalse(limiter.is_allowed())

    def test_very_short_period(self):
        """测试极短的周期"""
        limiter = RateLimiter(max_calls=2, period=0.1)

        self.assertTrue(limiter.is_allowed())
        self.assertTrue(limiter.is_allowed())
        self.assertFalse(limiter.is_allowed())

        time.sleep(0.15)

        # 应该恢复
        self.assertTrue(limiter.is_allowed())

    def test_large_max_calls(self):
        """测试大量调用限制"""
        limiter = RateLimiter(max_calls=1000, period=1)

        # 应该能连续调用1000次
        for _ in range(1000):
            self.assertTrue(limiter.is_allowed())

        # 第1001次被拒绝
        self.assertFalse(limiter.is_allowed())

    def test_concurrent_status_checks(self):
        """测试并发状态检查"""
        limiter = RateLimiter(max_calls=5, period=60)

        limiter.is_allowed()
        limiter.is_allowed()

        # 多次get_status不应该影响状态
        status1 = limiter.get_status()
        status2 = limiter.get_status()
        status3 = limiter.get_status()

        self.assertEqual(status1["used"], 2)
        self.assertEqual(status2["used"], 2)
        self.assertEqual(status3["used"], 2)


if __name__ == "__main__":
    unittest.main()
