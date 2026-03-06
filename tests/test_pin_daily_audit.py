import datetime as dt
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

# pin_daily_audit.py 依赖 message_renderer；当前仓库缺失该文件时，测试环境注入最小桩实现
if "message_renderer" not in sys.modules:
    stub_module = types.ModuleType("message_renderer")

    class MessageToDocxConverter:  # noqa: N801
        def __init__(self, docx_storage):  # noqa: D401, ARG002
            self.docx_storage = docx_storage

        def convert(self, raw_content, message_id, doc_token, sender_name=None, send_time=None):  # noqa: ARG002
            return []

    stub_module.MessageToDocxConverter = MessageToDocxConverter
    sys.modules["message_renderer"] = stub_module

from pin_daily_audit import DailyPinAuditor


class DummyAuth:
    def get_headers(self):
        return {"Authorization": "Bearer test-token"}


class DummyStorage:
    pass


def _build_auditor(test_dir: Path):
    DailyPinAuditor.PROCESSED_FILE = test_dir / ".processed_daily_pins.txt"
    return DailyPinAuditor(DummyAuth(), DummyStorage(), "oc_test_chat")


def _make_test_dir() -> Path:
    test_dir = Path(".tmp") / f"pin_daily_audit_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def test_get_pinned_messages_supports_pagination():
    auditor = _build_auditor(_make_test_dir())

    page1 = Mock()
    page1.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"message_id": "m1", "create_time": "1739836800000"}],
            "page_token": "next_page",
        },
    }
    page2 = Mock()
    page2.json.return_value = {
        "code": 0,
        "data": {
            "items": [{"message_id": "m2", "create_time": "1739840400000"}],
            "page_token": None,
        },
    }

    with patch("pin_daily_audit.requests.get", side_effect=[page1, page2]) as mock_get:
        pins = auditor._get_pinned_messages()

    assert pins is not None
    assert [p["message_id"] for p in pins] == ["m1", "m2"]
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["params"] == {
        "chat_id": "oc_test_chat",
        "page_size": DailyPinAuditor.MAX_PIN_PAGE_SIZE,
    }
    assert mock_get.call_args_list[1].kwargs["params"] == {
        "chat_id": "oc_test_chat",
        "page_size": DailyPinAuditor.MAX_PIN_PAGE_SIZE,
        "page_token": "next_page",
    }


def test_run_for_last_week_accepts_second_timestamp():
    auditor = _build_auditor(_make_test_dir())

    week_start = dt.datetime(2026, 2, 16, 0, 0, 0)
    week_end = dt.datetime(2026, 2, 23, 0, 0, 0)
    pin_time_seconds = int(dt.datetime(2026, 2, 20, 12, 30, 0).timestamp())

    auditor._get_pinned_messages = Mock(
        return_value=[{"message_id": "m_sec", "operator_id": "ou_admin", "create_time": str(pin_time_seconds)}]
    )
    auditor._process_one_pin = Mock(
        return_value={
            "message_id": "m_sec",
            "sender_name": "Alice",
            "operator_name": "Admin",
            "pin_time": "2026-02-20 12:30:00",
            "content": "test content",
        }
    )
    auditor._save_processed_ids = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_last_week_window", return_value=(week_start, week_end)):
        processed = auditor.run_for_last_week()

    assert processed == 1
    auditor._process_one_pin.assert_called_once()
    assert "m_sec" in auditor.processed_ids
    auditor._send_summary_card.assert_called_once()


def test_run_for_last_week_with_two_pins_only_last_week_one_should_notify():
    auditor = _build_auditor(_make_test_dir())

    week_start = dt.datetime(2026, 2, 16, 0, 0, 0)
    week_end = dt.datetime(2026, 2, 23, 0, 0, 0)
    old_pin_ms = int(dt.datetime(2026, 2, 15, 10, 0, 0).timestamp() * 1000)
    last_week_pin_ms = int(dt.datetime(2026, 2, 19, 15, 45, 0).timestamp() * 1000)

    old_pin = {"message_id": "m_old", "operator_id": "ou_admin", "create_time": str(old_pin_ms)}
    last_week_pin = {"message_id": "m_new", "operator_id": "ou_admin", "create_time": str(last_week_pin_ms)}

    auditor._get_pinned_messages = Mock(return_value=[old_pin, last_week_pin])
    auditor._process_one_pin = Mock(
        return_value={
            "message_id": "m_new",
            "sender_name": "Bob",
            "operator_name": "Admin",
            "pin_time": "2026-02-19 15:45:00",
            "content": "last week pin",
        }
    )
    auditor._save_processed_ids = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_last_week_window", return_value=(week_start, week_end)):
        processed = auditor.run_for_last_week()

    assert processed == 1
    auditor._process_one_pin.assert_called_once_with(last_week_pin)
    auditor._send_summary_card.assert_called_once()


def test_run_for_last_week_if_pin_already_processed_should_not_notify():
    auditor = _build_auditor(_make_test_dir())

    week_start = dt.datetime(2026, 2, 16, 0, 0, 0)
    week_end = dt.datetime(2026, 2, 23, 0, 0, 0)
    last_week_pin_ms = int(dt.datetime(2026, 2, 21, 9, 30, 0).timestamp() * 1000)
    last_week_pin = {"message_id": "m_dup", "operator_id": "ou_admin", "create_time": str(last_week_pin_ms)}

    auditor.processed_ids = {"m_dup"}
    auditor._get_pinned_messages = Mock(return_value=[last_week_pin])
    auditor._process_one_pin = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_last_week_window", return_value=(week_start, week_end)):
        processed = auditor.run_for_last_week()

    assert processed == 0
    auditor._process_one_pin.assert_not_called()
    auditor._send_summary_card.assert_not_called()
