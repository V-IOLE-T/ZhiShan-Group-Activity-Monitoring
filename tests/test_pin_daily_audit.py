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


def _make_post_raw_content(rows, title="") -> str:
    return json.dumps(
        {"post": {"zh_cn": {"title": title, "content": rows}}},
        ensure_ascii=False,
    )


def _make_item(sender_name: str, post_time: str, raw_content: str, content: str = "") -> dict:
    return {
        "message_id": f"msg_{sender_name}",
        "sender_name": sender_name,
        "operator_name": "Admin",
        "post_time": post_time,
        "pin_time": "2026-02-21 12:00:00",
        "content": content or "fallback text",
        "raw_content": raw_content,
    }


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
            "raw_content": json.dumps({"text": "test content"}, ensure_ascii=False),
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
            "raw_content": json.dumps({"text": "last week pin"}, ensure_ascii=False),
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


def test_render_raw_content_to_card_markdown_preserves_paragraphs_and_rich_text():
    auditor = _build_auditor(_make_test_dir())
    raw_content = _make_post_raw_content(
        [
            [{"tag": "text", "text": "#个人思考"}],
            [{"tag": "text", "text": "加粗", "style": ["bold"]}, {"tag": "text", "text": "普通"}],
            [{"tag": "text", "text": "斜体", "style": ["italic"]}],
            [{"tag": "text", "text": "删除线", "style": ["lineThrough"]}],
            [{"tag": "a", "text": "查看详情", "href": "https://example.com"}],
            [{"tag": "at", "user_name": "小明"}],
            [{"tag": "text", "text": "1. 列表项"}],
            [{"tag": "img", "image_key": "img_xxx"}],
            [{"tag": "file", "file_key": "file_xxx"}],
        ]
    )

    markdown = auditor._render_raw_content_to_card_markdown(raw_content)

    assert "\\#个人思考" in markdown
    assert "**加粗**普通" in markdown
    assert "*斜体*" in markdown
    assert "~~删除线~~" in markdown
    assert "[查看详情](https://example.com)" in markdown
    assert "@小明" in markdown
    assert "1. 列表项" in markdown
    assert "[图片]" in markdown
    assert "[附件]" in markdown
    assert "\n\n" in markdown


def test_render_text_message_preserves_paragraphs_and_escapes_heading_marker():
    auditor = _build_auditor(_make_test_dir())
    raw_content = json.dumps(
        {"text": "#个人思考\n第一段\n\n第二段\n\n\n第三段"},
        ensure_ascii=False,
    )

    markdown = auditor._render_raw_content_to_card_markdown(raw_content)

    assert markdown.startswith("\\#个人思考")
    assert "第一段\n\n第二段\n\n第三段" in markdown


def test_build_summary_card_shows_all_previews_and_section_titles_when_collapsed():
    auditor = _build_auditor(_make_test_dir())
    items = [
        _make_item(
            "Alice",
            "2026-02-20 10:30:00",
            _make_post_raw_content(
                [
                    [{"tag": "text", "text": "#个人思考"}],
                    [{"tag": "text", "text": "A" * 220}],
                    [{"tag": "a", "text": "查看详情", "href": "https://example.com/a"}],
                    [{"tag": "text", "text": "1. 第一条内部列表"}],
                ]
            ),
        ),
        _make_item(
            "Bob",
            "2026-02-20 11:30:00",
            _make_post_raw_content(
                [
                    [{"tag": "text", "text": "B" * 220}],
                    [{"tag": "text", "text": "第二条补充说明"}],
                ]
            ),
        ),
        _make_item(
            "Carol",
            "2026-02-20 12:30:00",
            _make_post_raw_content(
                [
                    [{"tag": "text", "text": "C" * 160}],
                    [{"tag": "text", "text": "第三条补充说明"}],
                ]
            ),
        ),
    ]

    card = auditor._build_summary_card_payload(items, "📌 上周加精")
    body_elements = card["body"]["elements"]
    preview_markdowns = [element["content"] for element in body_elements if element["tag"] == "markdown"]
    panel = body_elements[-1]
    panel_markdowns = [element["content"] for element in panel["elements"] if element["tag"] == "markdown"]

    assert card["schema"] == "2.0"
    assert body_elements[-1]["tag"] == "collapsible_panel"
    assert len(preview_markdowns) == 4
    assert preview_markdowns[0] == "本次新增 3 条 Pin"
    assert "**【帖子一】Alice（02-20 10:30）**" in preview_markdowns[1]
    assert "**【帖子二】Bob（02-20 11:30）**" in preview_markdowns[2]
    assert "**【帖子三】Carol（02-20 12:30）**" in preview_markdowns[3]
    assert "](https://example.com/a)" not in preview_markdowns[1]
    assert "1. Alice" not in json.dumps(card, ensure_ascii=False)
    assert "2. Bob" not in json.dumps(card, ensure_ascii=False)
    assert len(panel_markdowns) == 3
    assert "\\#个人思考" in panel_markdowns[0]
    assert "[查看详情](https://example.com/a)" in panel_markdowns[0]
    assert "1. 第一条内部列表" in panel_markdowns[0]
    assert "B" * 220 in panel_markdowns[1]
    assert "C" * 160 in panel_markdowns[2]
    assert len([element for element in panel["elements"] if element["tag"] == "hr"]) == 2


def test_build_summary_card_respects_500_501_visible_text_boundary():
    auditor = _build_auditor(_make_test_dir())
    short_item = _make_item(
        "Alice",
        "2026-02-20 10:30:00",
        json.dumps({"text": "X" * 500}, ensure_ascii=False),
        content="X" * 500,
    )
    long_item = _make_item(
        "Alice",
        "2026-02-20 10:30:00",
        json.dumps({"text": "X" * 501}, ensure_ascii=False),
        content="X" * 501,
    )

    short_card = auditor._build_summary_card_payload([short_item], "📌 上周加精")
    long_card = auditor._build_summary_card_payload([long_item], "📌 上周加精")

    assert all(element["tag"] != "collapsible_panel" for element in short_card["body"]["elements"])
    assert long_card["body"]["elements"][-1]["tag"] == "collapsible_panel"


def test_send_summary_card_posts_interactive_payload():
    auditor = _build_auditor(_make_test_dir())
    items = [
        _make_item(
            "Alice",
            "2026-02-20 10:30:00",
            _make_post_raw_content(
                [
                    [{"tag": "text", "text": "#个人思考"}],
                    [{"tag": "text", "text": "hello world"}],
                ]
            ),
        )
    ]
    fake_response = Mock()
    fake_response.json.return_value = {"code": 0, "msg": "success"}

    with patch("pin_daily_audit.requests.post", return_value=fake_response) as mock_post:
        auditor._send_summary_card(items, "📌 上周加精")

    sent_body = mock_post.call_args.kwargs["json"]
    sent_card = json.loads(sent_body["content"])
    sent_payload = json.dumps(sent_card, ensure_ascii=False)

    assert sent_body["msg_type"] == "interactive"
    assert "**【帖子一】Alice（02-20 10:30）**" in sent_payload
    assert "\\#个人思考" in sent_payload
