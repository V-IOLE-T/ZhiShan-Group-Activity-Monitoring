import datetime as dt
from unittest.mock import Mock, patch

from pin_daily_audit import DailyPinAuditor


class DummyAuth:
    def get_headers(self):
        return {"Authorization": "Bearer test-token"}


class DummyStorage:
    pass


def _build_auditor(tmp_path, monkeypatch):
    monkeypatch.setattr(DailyPinAuditor, "PROCESSED_FILE", tmp_path / ".processed_daily_pins.txt")
    return DailyPinAuditor(DummyAuth(), DummyStorage(), "oc_test_chat")


def test_get_pinned_messages_supports_pagination(tmp_path, monkeypatch):
    auditor = _build_auditor(tmp_path, monkeypatch)

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
    assert mock_get.call_args_list[0].kwargs["params"] == {"chat_id": "oc_test_chat", "page_size": 100}
    assert mock_get.call_args_list[1].kwargs["params"] == {
        "chat_id": "oc_test_chat",
        "page_size": 100,
        "page_token": "next_page",
    }


def test_run_for_yesterday_accepts_second_timestamp(tmp_path, monkeypatch):
    auditor = _build_auditor(tmp_path, monkeypatch)

    y_start = dt.datetime(2026, 2, 23, 0, 0, 0)
    y_end = dt.datetime(2026, 2, 24, 0, 0, 0)
    pin_time_seconds = int(dt.datetime(2026, 2, 23, 12, 30, 0).timestamp())

    auditor._get_pinned_messages = Mock(
        return_value=[{"message_id": "m_sec", "operator_id": "ou_admin", "create_time": str(pin_time_seconds)}]
    )
    auditor._process_one_pin = Mock(
        return_value={
            "message_id": "m_sec",
            "sender_name": "Alice",
            "operator_name": "Admin",
            "pin_time": "2026-02-23 12:30:00",
            "content": "test content",
        }
    )
    auditor._save_processed_ids = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_yesterday_window", return_value=(y_start, y_end)):
        processed = auditor.run_for_yesterday()

    assert processed == 1
    auditor._process_one_pin.assert_called_once()
    assert "m_sec" in auditor.processed_ids
    auditor._send_summary_card.assert_called_once()


def test_run_for_yesterday_with_two_pins_only_yesterday_one_should_notify(tmp_path, monkeypatch):
    auditor = _build_auditor(tmp_path, monkeypatch)

    y_start = dt.datetime(2026, 2, 23, 0, 0, 0)
    y_end = dt.datetime(2026, 2, 24, 0, 0, 0)
    old_pin_ms = int(dt.datetime(2026, 2, 22, 10, 0, 0).timestamp() * 1000)
    yesterday_pin_ms = int(dt.datetime(2026, 2, 23, 15, 45, 0).timestamp() * 1000)

    old_pin = {"message_id": "m_old", "operator_id": "ou_admin", "create_time": str(old_pin_ms)}
    yesterday_pin = {"message_id": "m_new", "operator_id": "ou_admin", "create_time": str(yesterday_pin_ms)}

    auditor._get_pinned_messages = Mock(return_value=[old_pin, yesterday_pin])
    auditor._process_one_pin = Mock(
        return_value={
            "message_id": "m_new",
            "sender_name": "Bob",
            "operator_name": "Admin",
            "pin_time": "2026-02-23 15:45:00",
            "content": "yesterday pin",
        }
    )
    auditor._save_processed_ids = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_yesterday_window", return_value=(y_start, y_end)):
        processed = auditor.run_for_yesterday()

    assert processed == 1
    auditor._process_one_pin.assert_called_once_with(yesterday_pin)
    auditor._send_summary_card.assert_called_once()


def test_run_for_yesterday_if_yesterday_pin_already_processed_should_not_notify(tmp_path, monkeypatch):
    auditor = _build_auditor(tmp_path, monkeypatch)

    y_start = dt.datetime(2026, 2, 23, 0, 0, 0)
    y_end = dt.datetime(2026, 2, 24, 0, 0, 0)
    yesterday_pin_ms = int(dt.datetime(2026, 2, 23, 9, 30, 0).timestamp() * 1000)
    yesterday_pin = {"message_id": "m_dup", "operator_id": "ou_admin", "create_time": str(yesterday_pin_ms)}

    auditor.processed_ids = {"m_dup"}
    auditor._get_pinned_messages = Mock(return_value=[yesterday_pin])
    auditor._process_one_pin = Mock()
    auditor._send_summary_card = Mock()

    with patch.object(DailyPinAuditor, "_get_yesterday_window", return_value=(y_start, y_end)):
        processed = auditor.run_for_yesterday()

    assert processed == 0
    auditor._process_one_pin.assert_not_called()
    auditor._send_summary_card.assert_not_called()
