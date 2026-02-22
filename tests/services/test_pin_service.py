"""
PinService 单元测试

测试 Pin 处理服务的各种场景
"""

import pytest
from unittest.mock import Mock, patch
import requests
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.pin_service import PinService


class TestPinService:
    """PinService 测试类"""

    def test_extract_user_id_string(self):
        """测试从字符串提取用户 ID"""
        assert PinService.extract_user_id("ou_xxx") == "ou_xxx"
        assert PinService.extract_user_id("cli_xxx") == "cli_xxx"

    def test_extract_user_id_dict(self):
        """测试从字典提取用户 ID"""
        assert PinService.extract_user_id({"user_id": "ou_xxx"}) == "ou_xxx"
        assert PinService.extract_user_id({"open_id": "cli_xxx"}) == "cli_xxx"

    def test_extract_user_id_invalid(self):
        """测试无效输入"""
        assert PinService.extract_user_id(None) is None
        assert PinService.extract_user_id({}) is None
        assert PinService.extract_user_id([]) is None

    def test_format_timestamp_ms(self):
        """测试时间戳格式化"""
        # 2024-01-01 00:00:00 UTC = 1704067200000 ms
        result = PinService.format_timestamp_ms(1704067200000)
        assert "2024-01-01" in result

    def test_format_timestamp_ms_empty(self):
        """测试空时间戳"""
        assert PinService.format_timestamp_ms(0) == ""
        assert PinService.format_timestamp_ms(None) == ""

    def test_safe_int(self):
        """测试安全整数转换"""
        assert PinService.safe_int("123") == 123
        assert PinService.safe_int("abc", 99) == 99
        assert PinService.safe_int(None, 5) == 5
        assert PinService.safe_int(456) == 456

    @patch('services.pin_service.requests.get')
    def test_get_pinned_messages_success(self, mock_get):
        """测试获取 Pin 列表成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {"message_id": "msg1", "operator_id": "user1"},
                    {"message_id": "msg2", "operator_id": "user2"}
                ],
                "page_token": None
            }
        }
        mock_get.return_value = mock_response

        result = PinService.get_pinned_messages("chat_xxx", "Bearer token")
        assert len(result) == 2
        assert result[0]["message_id"] == "msg1"

    @patch('services.pin_service.requests.get')
    def test_get_pinned_messages_empty(self, mock_get):
        """测试获取空 Pin 列表"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [],
                "page_token": None
            }
        }
        mock_get.return_value = mock_response

        result = PinService.get_pinned_messages("chat_xxx", "Bearer token")
        assert len(result) == 0

    @patch('services.pin_service.requests.get')
    def test_get_pinned_messages_api_error(self, mock_get):
        """测试 API 错误"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": -1,
            "msg": "Invalid request"
        }
        mock_get.return_value = mock_response

        result = PinService.get_pinned_messages("chat_xxx", "Bearer token")
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
