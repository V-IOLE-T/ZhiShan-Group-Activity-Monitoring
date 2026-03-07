import datetime as dt
import json
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch


# pin_daily_audit.py 依赖 message_renderer；当前仓库缺失该文件时，测试环境注入最小桩实现
if "message_renderer" not in sys.modules:
    stub_module = types.ModuleType("message_renderer")

    class MessageToDocxConverter:  # noqa: N801
        def __init__(self, docx_storage):
            self.docx_storage = docx_storage

        def convert(self, raw_content, message_id, doc_token, sender_name=None, send_time=None):
            return [
                {
                    "type": "text",
                    "message_id": message_id,
                    "sender_name": sender_name,
                    "send_time": send_time,
                    "raw_content": raw_content,
                    "doc_token": doc_token,
                }
            ]

    stub_module.MessageToDocxConverter = MessageToDocxConverter
    sys.modules["message_renderer"] = stub_module

from pin_daily_audit import DailyPinAuditor


class DummyAuth:
    def get_headers(self):
        return {"Authorization": "Bearer test-token"}


class FakeStorage:
    def __init__(self):
        self.archived_pin_messages = []
        self.pin_count_updates = []

    def archive_pin_message(self, pin_info):
        self.archived_pin_messages.append(pin_info)
        return True

    def increment_pin_count(self, user_id, user_name):
        self.pin_count_updates.append({"user_id": user_id, "user_name": user_name})
        return True


class FakeDocxStorage:
    def __init__(self):
        self.blocks_calls = []

    def add_blocks(self, doc_token, blocks):
        self.blocks_calls.append({"doc_token": doc_token, "blocks": blocks})
        return True


class TestPinAuditEnvironment(unittest.TestCase):
    def setUp(self):
        self.storage = FakeStorage()
        self.docx_storage = FakeDocxStorage()

        test_processed_file = Path(tempfile.gettempdir()) / f".tmp_processed_daily_pins_{uuid.uuid4().hex}.txt"
        if test_processed_file.exists():
            test_processed_file.unlink()

        DailyPinAuditor.PROCESSED_FILE = test_processed_file
        self.auditor = DailyPinAuditor(
            auth=DummyAuth(),
            storage=self.storage,
            chat_id="oc_test_chat",
            docx_storage=self.docx_storage,
            essence_doc_token="doc_test_token",
        )

    def tearDown(self):
        if DailyPinAuditor.PROCESSED_FILE.exists():
            DailyPinAuditor.PROCESSED_FILE.unlink()

    def test_weekly_pin_audit_success_flow_with_stubbed_feishu_api(self):
        """
        测试环境目标：
        1. 用假 API 跑通上周 Pin 处理完整链路
        2. 验证拉取 Pin 的 page_size 为 50
        3. 验证归档/计数/精华文档/汇总卡片都被触发
        """
        this_week_start = dt.datetime(2026, 2, 23, 0, 0, 0)
        last_week_start = this_week_start - dt.timedelta(days=7)
        last_week_end = this_week_start

        last_week_pin_ms = int(dt.datetime(2026, 2, 20, 10, 30, 0).timestamp() * 1000)
        old_pin_ms = int(dt.datetime(2026, 2, 23, 9, 0, 0).timestamp() * 1000)

        all_get_calls = []

        def fake_get(url, headers=None, params=None, timeout=10):  # noqa: ARG001
            all_get_calls.append({"url": url, "params": params})

            if url.endswith("/im/v1/pins"):
                response = Mock()
                response.json.return_value = {
                    "code": 0,
                    "data": {
                        "items": [
                            {"message_id": "msg_last_week", "operator_id": "ou_admin", "create_time": str(last_week_pin_ms)},
                            {"message_id": "msg_old", "operator_id": "ou_admin", "create_time": str(old_pin_ms)},
                        ],
                        "page_token": None,
                    },
                }
                return response

            if "/im/v1/messages/" in url:
                response = Mock()
                response.json.return_value = {
                    "code": 0,
                    "data": {
                        "items": [
                            {
                                "sender": {"id": {"open_id": "ou_sender_1"}},
                                "msg_type": "text",
                                "body": {"content": '{"text":"hello pin"}'},
                                "create_time": str(last_week_pin_ms),
                            }
                        ]
                    },
                }
                return response

            raise AssertionError(f"unexpected GET url: {url}")

        fake_post_response = Mock()
        fake_post_response.json.return_value = {"code": 0, "msg": "success"}

        with (
            patch("pin_daily_audit.requests.get", side_effect=fake_get),
            patch("pin_daily_audit.requests.post", return_value=fake_post_response) as mock_post,
            patch.object(DailyPinAuditor, "_get_last_week_window", return_value=(last_week_start, last_week_end)),
            patch.object(self.auditor.collector, "get_user_names", return_value={"ou_sender_1": "Alice", "ou_admin": "Admin"}),
        ):
            processed_count = self.auditor.run_for_last_week()

        self.assertEqual(processed_count, 1)
        self.assertEqual(len(self.storage.archived_pin_messages), 1)
        self.assertEqual(len(self.storage.pin_count_updates), 1)
        self.assertEqual(len(self.docx_storage.blocks_calls), 1)
        self.assertEqual(mock_post.call_count, 1)
        self.assertIn("msg_last_week", self.auditor.processed_ids)
        self.assertNotIn("msg_old", self.auditor.processed_ids)

        sent_body = mock_post.call_args.kwargs["json"]
        sent_card = json.loads(sent_body["content"])
        sent_text = sent_card["body"]["elements"][0]["content"]
        self.assertEqual(sent_body["msg_type"], "interactive")
        self.assertIn("Alice（02-20 10:30）", sent_text)
        self.assertNotIn("Admin", sent_text)

        first_get = all_get_calls[0]
        self.assertTrue(first_get["url"].endswith("/im/v1/pins"))
        self.assertEqual(first_get["params"]["page_size"], DailyPinAuditor.MAX_PIN_PAGE_SIZE)

    def test_weekly_pin_audit_should_stop_when_pin_list_api_returns_error(self):
        """
        测试环境目标：
        模拟 Pin 列表接口报错，确保任务安全退出，不做后续写入。
        """
        failed_get_response = Mock()
        failed_get_response.json.return_value = {
            "code": 99992402,
            "msg": "field validation failed",
        }

        with (
            patch("pin_daily_audit.requests.get", return_value=failed_get_response),
            patch("pin_daily_audit.requests.post") as mock_post,
        ):
            processed_count = self.auditor.run_for_last_week()

        self.assertEqual(processed_count, 0)
        self.assertEqual(len(self.storage.archived_pin_messages), 0)
        self.assertEqual(len(self.storage.pin_count_updates), 0)
        self.assertEqual(mock_post.call_count, 0)

    def test_get_pinned_messages_should_paginate_with_page_token(self):
        """
        测试环境目标：
        验证 Pin 列表分页拉取，且每页 page_size 都是 50。
        """
        page1 = Mock()
        page1.json.return_value = {
            "code": 0,
            "data": {
                "items": [{"message_id": "m1", "create_time": "1700000000000"}],
                "page_token": "next_page_token",
            },
        }
        page2 = Mock()
        page2.json.return_value = {
            "code": 0,
            "data": {
                "items": [{"message_id": "m2", "create_time": "1700003600000"}],
                "page_token": None,
            },
        }

        with patch("pin_daily_audit.requests.get", side_effect=[page1, page2]) as mock_get:
            pins = self.auditor._get_pinned_messages()

        self.assertEqual([p["message_id"] for p in pins], ["m1", "m2"])
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["page_size"], DailyPinAuditor.MAX_PIN_PAGE_SIZE)
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["page_size"], DailyPinAuditor.MAX_PIN_PAGE_SIZE)
        self.assertEqual(mock_get.call_args_list[1].kwargs["params"]["page_token"], "next_page_token")


if __name__ == "__main__":
    unittest.main(verbosity=2)
