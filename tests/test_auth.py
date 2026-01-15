"""
auth.py 单元测试

测试飞书API认证模块的token获取、刷新和缓存逻辑
"""

import unittest
import time
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
import requests


class TestFeishuAuth(unittest.TestCase):
    """测试FeishuAuth类"""

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    def test_initialization_success(self):
        """测试成功初始化"""
        from auth import FeishuAuth

        auth = FeishuAuth()

        self.assertEqual(auth.app_id, "test_app_id")
        self.assertEqual(auth.app_secret, "test_secret")
        self.assertIsNone(auth.tenant_access_token)
        self.assertEqual(auth.token_expire_time, 0)

    @patch.dict("os.environ", {}, clear=True)
    def test_initialization_missing_app_id(self):
        """测试APP_ID缺失时抛出异常"""
        from auth import FeishuAuth

        with self.assertRaises(ValueError) as context:
            FeishuAuth()

        self.assertIn("APP_ID和APP_SECRET必须在.env文件中配置", str(context.exception))

    @patch.dict("os.environ", {"APP_ID": "test_id"}, clear=True)
    def test_initialization_missing_app_secret(self):
        """测试APP_SECRET缺失时抛出异常"""
        from auth import FeishuAuth

        with self.assertRaises(ValueError) as context:
            FeishuAuth()

        self.assertIn("APP_ID和APP_SECRET必须在.env文件中配置", str(context.exception))

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_first_time(self, mock_post):
        """测试首次获取token"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()
        token = auth.get_tenant_access_token()

        # 验证返回值
        self.assertEqual(token, "test_token_123")
        self.assertEqual(auth.tenant_access_token, "test_token_123")

        # 验证token过期时间（应该是当前时间 + 7200 - 300秒）
        expected_expire = datetime.now().timestamp() + 7200 - 300
        self.assertAlmostEqual(auth.token_expire_time, expected_expire, delta=5)

        # 验证API调用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["json"]["app_id"], "test_app_id")
        self.assertEqual(call_args[1]["json"]["app_secret"], "test_secret")

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_cached(self, mock_post):
        """测试缓存的token直接返回，不调用API"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        # 第一次调用
        token1 = auth.get_tenant_access_token()
        self.assertEqual(mock_post.call_count, 1)

        # 第二次调用应该使用缓存，不调用API
        token2 = auth.get_tenant_access_token()
        self.assertEqual(mock_post.call_count, 1)  # 仍然是1次

        self.assertEqual(token1, token2)

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_force_refresh(self, mock_post):
        """测试强制刷新token"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        # 第一次调用
        token1 = auth.get_tenant_access_token()
        self.assertEqual(mock_post.call_count, 1)

        # 强制刷新
        token2 = auth.get_tenant_access_token(force_refresh=True)
        self.assertEqual(mock_post.call_count, 2)  # 应该调用2次

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_expired(self, mock_post):
        """测试token过期后自动刷新"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 1,  # 1秒后过期
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        # 第一次调用
        token1 = auth.get_tenant_access_token()
        self.assertEqual(mock_post.call_count, 1)

        # 等待token过期（1秒 - 300秒提前量 < 0，立即过期）
        # 由于提前5分钟刷新，token已经是过期状态

        # 第二次调用应该刷新token
        token2 = auth.get_tenant_access_token()
        self.assertEqual(mock_post.call_count, 2)

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_api_error(self, mock_post):
        """测试API返回错误"""
        from auth import FeishuAuth

        # Mock API错误响应
        mock_response = Mock()
        mock_response.json.return_value = {"code": 99991663, "msg": "App ID not found"}
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        with self.assertRaises(Exception) as context:
            auth.get_tenant_access_token()

        self.assertIn("获取token失败", str(context.exception))
        self.assertIn("99991663", str(context.exception))

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_timeout(self, mock_post):
        """测试请求超时"""
        from auth import FeishuAuth

        # Mock超时异常
        mock_post.side_effect = requests.exceptions.Timeout()

        auth = FeishuAuth()

        with self.assertRaises(Exception) as context:
            auth.get_tenant_access_token()

        self.assertIn("超时", str(context.exception))

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_token_network_error(self, mock_post):
        """测试网络错误"""
        from auth import FeishuAuth

        # Mock网络异常
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        auth = FeishuAuth()

        with self.assertRaises(Exception) as context:
            auth.get_tenant_access_token()

        self.assertIn("请求失败", str(context.exception))

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_headers_basic(self, mock_post):
        """测试get_headers基本功能"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()
        headers = auth.get_headers()

        # 验证headers格式
        self.assertEqual(headers["Authorization"], "Bearer test_token_123")
        self.assertEqual(headers["Content-Type"], "application/json")

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_headers_auto_refresh(self, mock_post):
        """测试get_headers在token过期时自动刷新"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 1,  # 1秒后过期（提前5分钟=立即过期）
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        # 第一次获取headers
        headers1 = auth.get_headers()
        self.assertEqual(mock_post.call_count, 1)

        # token已过期，get_headers应该自动刷新
        headers2 = auth.get_headers()
        self.assertEqual(mock_post.call_count, 2)

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_get_headers_uses_cached_token(self, mock_post):
        """测试get_headers使用缓存的有效token"""
        from auth import FeishuAuth

        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()

        # 第一次获取headers
        headers1 = auth.get_headers()
        self.assertEqual(mock_post.call_count, 1)

        # 第二次应该使用缓存，不调用API
        headers2 = auth.get_headers()
        self.assertEqual(mock_post.call_count, 1)

        # Headers应该相同
        self.assertEqual(headers1, headers2)

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_token_expiry_calculation(self, mock_post):
        """测试token过期时间计算（提前5分钟）"""
        from auth import FeishuAuth

        # Mock API响应，expire=7200秒
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
        }
        mock_post.return_value = mock_response

        auth = FeishuAuth()
        before_call = datetime.now().timestamp()
        auth.get_tenant_access_token()
        after_call = datetime.now().timestamp()

        # 过期时间应该是：当前时间 + 7200 - 300（提前5分钟）
        expected_min = before_call + 7200 - 300
        expected_max = after_call + 7200 - 300

        self.assertGreaterEqual(auth.token_expire_time, expected_min)
        self.assertLessEqual(auth.token_expire_time, expected_max)


class TestAuthIntegration(unittest.TestCase):
    """集成测试 - 测试完整的token生命周期"""

    @patch.dict("os.environ", {"APP_ID": "test_app_id", "APP_SECRET": "test_secret"})
    @patch("auth.requests.post")
    def test_full_token_lifecycle(self, mock_post):
        """测试完整的token生命周期：获取 -> 缓存 -> 过期 -> 刷新"""
        from auth import FeishuAuth

        # Mock API响应
        call_count = [0]

        def mock_api_call(*args, **kwargs):
            call_count[0] += 1
            mock_response = Mock()
            mock_response.json.return_value = {
                "code": 0,
                "tenant_access_token": f"token_{call_count[0]}",
                "expire": 7200,
            }
            return mock_response

        mock_post.side_effect = mock_api_call

        auth = FeishuAuth()

        # 1. 首次获取token
        token1 = auth.get_tenant_access_token()
        self.assertEqual(token1, "token_1")
        self.assertEqual(call_count[0], 1)

        # 2. 使用缓存的token
        token2 = auth.get_tenant_access_token()
        self.assertEqual(token2, "token_1")
        self.assertEqual(call_count[0], 1)  # 没有新的API调用

        # 3. 强制刷新
        token3 = auth.get_tenant_access_token(force_refresh=True)
        self.assertEqual(token3, "token_2")
        self.assertEqual(call_count[0], 2)

        # 4. get_headers使用最新token
        headers = auth.get_headers()
        self.assertEqual(headers["Authorization"], "Bearer token_2")
        self.assertEqual(call_count[0], 2)  # 没有新的API调用


if __name__ == "__main__":
    unittest.main()
