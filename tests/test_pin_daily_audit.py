import datetime as dt
import json
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
            "post_time": "2026-02-20 09:00:00",
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
            "post_time": "2026-02-19 10:00:00",
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


def test_build_summary_card_shows_full_posts_without_panel_when_within_threshold():
    auditor = _build_auditor(_make_test_dir())
    items = [
        {
            "message_id": "m1",
            "sender_name": "Alice",
            "operator_name": "Admin",
            "post_time": "2026-02-20 10:30:00",
            "pin_time": "2026-02-21 12:00:00",
            "content": "短内容",
        }
    ]

    card = auditor._build_summary_card_payload(items, "📌 上周加精")

    assert card["schema"] == "2.0"
    assert card["body"]["elements"][0]["tag"] == "markdown"
    assert "collapsible_panel" not in json.dumps(card, ensure_ascii=False)
    assert "02-20 10:30" in card["body"]["elements"][0]["content"]
    assert "02-21 12:00" not in card["body"]["elements"][0]["content"]


def test_build_summary_card_wraps_long_posts_in_collapsible_panel():
    auditor = _build_auditor(_make_test_dir())
    items = [
        {
            "message_id": "m1",
            "sender_name": "Alice",
            "operator_name": "Admin",
            "post_time": "2026-02-20 10:30:00",
            "pin_time": "2026-02-21 12:00:00",
            "content": "A" * 260,
        },
        {
            "message_id": "m2",
            "sender_name": "Bob",
            "operator_name": "Admin",
            "post_time": "2026-02-20 11:30:00",
            "pin_time": "2026-02-21 13:00:00",
            "content": "B" * 260,
        },
        {
            "message_id": "m3",
            "sender_name": "Carol",
            "operator_name": "Admin",
            "post_time": "2026-02-20 12:30:00",
            "pin_time": "2026-02-21 14:00:00",
            "content": "C" * 80,
        },
    ]

    card = auditor._build_summary_card_payload(items, "📌 上周加精")
    body_elements = card["body"]["elements"]
    preview_element = body_elements[0]
    panel_element = body_elements[1]
    panel_text = panel_element["elements"][0]["content"]

    assert len(body_elements) == 2
    assert preview_element["tag"] == "markdown"
    assert panel_element["tag"] == "collapsible_panel"
    assert panel_element["expanded"] is False
    assert panel_element["header"]["title"]["content"] == DailyPinAuditor.PIN_SUMMARY_COLLAPSIBLE_TITLE
    assert "Alice（02-20 10:30）" in preview_element["content"]
    assert "Bob（02-20 11:30）" in preview_element["content"]
    assert "Carol" not in preview_element["content"]
    assert ("A" * DailyPinAuditor.PIN_SUMMARY_PREVIEW_LENGTH) + "..." in preview_element["content"]
    assert ("B" * DailyPinAuditor.PIN_SUMMARY_PREVIEW_LENGTH) + "..." in preview_element["content"]
    assert "02-21 12:00" not in preview_element["content"]
    assert "02-21 13:00" not in preview_element["content"]
    assert "Alice（02-20 10:30）" in panel_text
    assert "Bob（02-20 11:30）" in panel_text
    assert "Carol（02-20 12:30）" in panel_text
    assert "A" * 260 in panel_text
    assert "B" * 260 in panel_text
    assert "C" * 80 in panel_text


def test_build_summary_card_respects_500_501_threshold_boundary():
    auditor = _build_auditor(_make_test_dir())
    detail_prefix = "1. Alice（02-20 10:30）\n"
    exact_500_content = "X" * (DailyPinAuditor.PIN_SUMMARY_COLLAPSE_THRESHOLD - len(detail_prefix))
    overflow_content = exact_500_content + "Y"

    short_card = auditor._build_summary_card_payload(
        [
            {
                "message_id": "m1",
                "sender_name": "Alice",
                "operator_name": "Admin",
                "post_time": "2026-02-20 10:30:00",
                "pin_time": "2026-02-21 12:00:00",
                "content": exact_500_content,
            }
        ],
        "📌 上周加精",
    )
    long_card = auditor._build_summary_card_payload(
        [
            {
                "message_id": "m1",
                "sender_name": "Alice",
                "operator_name": "Admin",
                "post_time": "2026-02-20 10:30:00",
                "pin_time": "2026-02-21 12:00:00",
                "content": overflow_content,
            }
        ],
        "📌 上周加精",
    )

    assert len(short_card["body"]["elements"]) == 1
    assert short_card["body"]["elements"][0]["tag"] == "markdown"
    assert len(long_card["body"]["elements"]) == 2
    assert long_card["body"]["elements"][1]["tag"] == "collapsible_panel"


def test_send_summary_card_posts_interactive_payload():
    auditor = _build_auditor(_make_test_dir())
    items = [
        {
            "message_id": "m1",
            "sender_name": "Alice",
            "operator_name": "Admin",
            "post_time": "2026-02-20 10:30:00",
            "pin_time": "2026-02-21 12:00:00",
            "content": "hello world",
        }
    ]
    fake_response = Mock()
    fake_response.json.return_value = {"code": 0, "msg": "success"}

    with patch("pin_daily_audit.requests.post", return_value=fake_response) as mock_post:
        auditor._send_summary_card(items, "📌 上周加精")

    sent_body = mock_post.call_args.kwargs["json"]
    sent_card = json.loads(sent_body["content"])
    assert sent_body["msg_type"] == "interactive"
    assert sent_card["body"]["elements"][0]["tag"] == "markdown"
