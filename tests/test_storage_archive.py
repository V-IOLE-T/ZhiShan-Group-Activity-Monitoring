import re
from unittest.mock import patch
from unittest.mock import Mock

from storage import MessageArchiveStorage


class DummyAuth:
    def get_headers(self):
        return {"Authorization": "Bearer test"}


def test_save_message_returns_false_when_archive_not_configured():
    storage = MessageArchiveStorage(DummyAuth())
    storage.app_token = None
    storage.archive_table_id = None

    with patch("storage.requests.post") as mock_post:
        ok = storage.save_message({"消息ID": "om_test"})

    assert ok is False
    mock_post.assert_not_called()


def test_save_message_with_minimal_announcement_fields():
    storage = MessageArchiveStorage(DummyAuth())
    storage.app_token = "app_test"
    storage.archive_table_id = "tbl_test"

    response = Mock()
    response.json.return_value = {"code": 0, "msg": "success"}

    fields = {
        "消息ID": "om_xxx",
        "话题ID": "om_root",
        "发送者姓名": "张三",
        "消息内容": "#公告 内容",
        "发送时间": "2026-02-24 12:34:56",
    }

    with patch("storage.requests.post", return_value=response) as mock_post:
        ok = storage.save_message(fields)

    assert ok is True
    sent_payload = mock_post.call_args.kwargs["json"]["fields"]
    assert set(sent_payload.keys()) == {"消息ID", "话题ID", "发送者姓名", "消息内容", "发送时间"}
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", sent_payload["发送时间"])
