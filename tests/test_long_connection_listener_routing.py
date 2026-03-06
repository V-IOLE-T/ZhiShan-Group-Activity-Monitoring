import importlib
import json
import sys
import time
import types
import unittest
from types import SimpleNamespace


def _install_listener_stubs():
    # storage.py is absent in repo; provide minimal runtime stub for listener import.
    storage_stub = types.ModuleType("storage")

    class BitableStorage:  # noqa: N801
        def __init__(self, auth):  # noqa: ARG002
            self.calls = []

        def update_or_create_record(self, user_id, user_name, metrics_delta):
            self.calls.append(
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "metrics_delta": metrics_delta,
                }
            )
            return True

    class MessageArchiveStorage:  # noqa: N801
        def __init__(self, auth):  # noqa: ARG002
            self.archive_table_id = None

        def save_message(self, fields):  # noqa: ARG002
            return True

        def download_message_resource(self, message_id, resource_key, resource_type):  # noqa: ARG002
            return None

        def upload_file_to_drive(self, file_bin, file_name):  # noqa: ARG002
            return None

    class DocxStorage:  # noqa: N801
        def __init__(self, auth):  # noqa: ARG002
            pass

        def add_blocks(self, doc_token, blocks, insert_before_divider=False):  # noqa: ARG002
            return True

    storage_stub.BitableStorage = BitableStorage
    storage_stub.MessageArchiveStorage = MessageArchiveStorage
    storage_stub.DocxStorage = DocxStorage
    sys.modules["storage"] = storage_stub

    # message_renderer.py is absent in repo; provide minimal converter.
    message_renderer_stub = types.ModuleType("message_renderer")

    class MessageToDocxConverter:  # noqa: N801
        def __init__(self, docx_storage):  # noqa: ARG002
            pass

        def convert(self, raw_content, message_id, doc_token, **kwargs):  # noqa: ARG002
            return []

    message_renderer_stub.MessageToDocxConverter = MessageToDocxConverter
    sys.modules["message_renderer"] = message_renderer_stub

    # health_monitor is imported lazily inside handlers; provide no-op hooks.
    health_monitor_stub = types.ModuleType("health_monitor")
    health_monitor_stub.status = {"total_events_processed": 0}
    health_monitor_stub.update_event_processed = lambda *_args, **_kwargs: None
    health_monitor_stub.start_health_monitor = lambda *args, **kwargs: None
    health_monitor_stub.update_websocket_connected = lambda *_args, **_kwargs: None
    health_monitor_stub.set_pin_monitor_status = lambda *_args, **_kwargs: None
    health_monitor_stub.health_monitor = health_monitor_stub
    sys.modules["health_monitor"] = health_monitor_stub

    # Ensure announcement service can be imported even when services package path is not resolved.
    services_pkg = sys.modules.get("services", types.ModuleType("services"))
    announcement_stub = types.ModuleType("services.announcement_service")

    class AnnouncementService:  # noqa: N801
        @staticmethod
        def parse_tags(raw_tags):
            if not raw_tags:
                return ["公告", "通知"]
            return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

        @staticmethod
        def is_announcement_message(content, tags=None):  # noqa: ARG002
            return False

    announcement_stub.AnnouncementService = AnnouncementService
    sys.modules["services"] = services_pkg
    sys.modules["services.announcement_service"] = announcement_stub


class _RecordingStorage:
    def __init__(self):
        self.calls = []

    def update_or_create_record(self, user_id, user_name, metrics_delta):
        self.calls.append(
            {
                "user_id": user_id,
                "user_name": user_name,
                "metrics_delta": metrics_delta,
            }
        )
        return True


class _RecordingDocxStorage:
    def __init__(self, raise_on_add=False):
        self.calls = []
        self.attempts = 0
        self.raise_on_add = raise_on_add

    def add_blocks(self, doc_token, blocks, insert_before_divider=False):
        self.attempts += 1
        if self.raise_on_add:
            raise RuntimeError("doc add failure")
        self.calls.append(
            {
                "doc_token": doc_token,
                "blocks": blocks,
                "insert_before_divider": insert_before_divider,
            }
        )
        return True


class TestLongConnectionListenerRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._module_backup = {
            "storage": sys.modules.get("storage"),
            "message_renderer": sys.modules.get("message_renderer"),
            "health_monitor": sys.modules.get("health_monitor"),
            "services": sys.modules.get("services"),
            "services.announcement_service": sys.modules.get("services.announcement_service"),
        }
        _install_listener_stubs()

    @classmethod
    def tearDownClass(cls):
        for name, original in cls._module_backup.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def setUp(self):
        if "long_connection_listener" in sys.modules:
            del sys.modules["long_connection_listener"]

        self.listener = importlib.import_module("long_connection_listener")
        self.listener.CHAT_ID = "oc_test_chat"
        self.listener.ARCHIVE_DOC_TOKEN = "doc_default"
        self.listener.TAG_MAPPING["个人思考"] = "doc_thinking"
        self.listener.processed_events.clear()
        self.listener.message_metric_snapshots.clear()
        self.listener.recalled_messages_rolled_back.clear()
        self.listener.pending_updates.clear()
        self.listener.message_counter = 0
        self.listener.last_flush_ts = time.time()
        self.listener.user_name_cache.clear()

    @staticmethod
    def _message_with_post_text(text, message_id="om_test"):
        content = json.dumps(
            {
                "title": "",
                "content": [[{"tag": "text", "text": text, "style": []}]],
            },
            ensure_ascii=False,
        )
        return SimpleNamespace(
            content=content,
            parent_id=None,
            root_id=None,
            message_id=message_id,
            chat_id="oc_test_chat",
        )

    def _build_group_receive_event(self, text, message_id):
        message = self._message_with_post_text(text, message_id=message_id)
        message.chat_type = "group"
        message.chat_id = "oc_test_chat"
        message.message_type = "post"
        message.create_time = str(int(time.time() * 1000))
        message.mentions = []
        message.parent_id = None
        message.root_id = None
        return SimpleNamespace(
            header=SimpleNamespace(
                event_id=f"evt_{message_id}",
                event_type="im.message.receive_v1",
            ),
            event=SimpleNamespace(
                message=message,
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(open_id="ou_sender"),
                ),
            ),
        )

    def _assert_sender_metrics_accumulated(self, sender_id="ou_sender"):
        self.assertIn(sender_id, self.listener.pending_updates)
        metrics = self.listener.pending_updates[sender_id]["metrics"]
        self.assertGreaterEqual(metrics["message_count"], 1)
        self.assertGreaterEqual(metrics["char_count"], 1)

    def test_unknown_hashtag_does_not_archive_doc(self):
        msg = self._message_with_post_text("＃日常思考。今天记录一下")

        token, matched_tag, route_info = self.listener.get_target_doc_token(msg)

        self.assertIsNone(token)
        self.assertEqual(matched_tag, "默认")
        self.assertIn("日常思考", route_info["normalized_tags"])
        self.assertFalse(route_info["fallback"])
        self.assertEqual(route_info["reason"], "unknown_hashtag_no_archive")

    def test_no_hashtag_skips_archive(self):
        msg = self._message_with_post_text("今天只是普通发言，没有标签")

        token, matched_tag, route_info = self.listener.get_target_doc_token(msg)

        self.assertIsNone(token)
        self.assertEqual(matched_tag, "默认")
        self.assertEqual(route_info["reason"], "no_hashtag")

    def test_known_hashtag_routes_to_mapped_doc(self):
        msg = self._message_with_post_text("#个人思考 今天复盘")

        token, matched_tag, route_info = self.listener.get_target_doc_token(msg)

        self.assertEqual(token, "doc_thinking")
        self.assertEqual(matched_tag, "个人思考")
        self.assertTrue(route_info["matched"])
        self.assertEqual(route_info["reason"], "matched_tag")

    def test_receive_unknown_hashtag_skips_archive_but_accumulates_activity(self):
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        docx_recorder = _RecordingDocxStorage()
        self.listener.docx_storage = docx_recorder

        data = self._build_group_receive_event("＃日常思考。今天记录一下", "om_unknown")
        self.listener.do_p2_im_message_receive_v1(data)

        self.assertEqual(len(docx_recorder.calls), 0)
        self._assert_sender_metrics_accumulated()

    def test_receive_no_hashtag_skips_archive_but_accumulates_activity(self):
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        docx_recorder = _RecordingDocxStorage()
        self.listener.docx_storage = docx_recorder

        data = self._build_group_receive_event("今天只是普通发言，没有标签", "om_no_tag")
        self.listener.do_p2_im_message_receive_v1(data)

        self.assertEqual(len(docx_recorder.calls), 0)
        self._assert_sender_metrics_accumulated()

    def test_receive_known_hashtag_archives_doc_and_accumulates_activity(self):
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        docx_recorder = _RecordingDocxStorage()
        self.listener.docx_storage = docx_recorder

        data = self._build_group_receive_event("#个人思考 今天复盘", "om_known_tag")
        self.listener.do_p2_im_message_receive_v1(data)

        self.assertEqual(len(docx_recorder.calls), 1)
        self.assertEqual(docx_recorder.calls[0]["doc_token"], "doc_thinking")
        self._assert_sender_metrics_accumulated()

    def test_receive_doc_archive_error_still_accumulates_activity(self):
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        docx_recorder = _RecordingDocxStorage(raise_on_add=True)
        self.listener.docx_storage = docx_recorder

        data = self._build_group_receive_event("#个人思考 今天复盘", "om_archive_error")
        self.listener.do_p2_im_message_receive_v1(data)

        self.assertEqual(docx_recorder.attempts, 1)
        self.assertEqual(len(docx_recorder.calls), 0)
        self._assert_sender_metrics_accumulated()

    def test_receive_tag_parse_error_skips_archive_but_accumulates_activity(self):
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        docx_recorder = _RecordingDocxStorage()
        self.listener.docx_storage = docx_recorder

        def _raise_tag_parse_error(_message):
            raise RuntimeError("tag parse failure")

        original_get_target_doc_token = self.listener.get_target_doc_token
        self.listener.get_target_doc_token = _raise_tag_parse_error
        try:
            data = self._build_group_receive_event("#个人思考 今天复盘", "om_tag_parse_error")
            self.listener.do_p2_im_message_receive_v1(data)
        finally:
            self.listener.get_target_doc_token = original_get_target_doc_token

        self.assertEqual(len(docx_recorder.calls), 0)
        self._assert_sender_metrics_accumulated()

    def test_reaction_deleted_rolls_back_reaction_metrics(self):
        recorder = _RecordingStorage()
        self.listener.storage = recorder
        self.listener.collector.get_message_sender = lambda _message_id: "ou_receiver"
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        self.listener.processed_events.clear()

        data = SimpleNamespace(
            header=SimpleNamespace(
                event_id="evt_reaction_deleted_1",
                event_type="im.message.reaction.deleted_v1",
            ),
            event=SimpleNamespace(
                user_id=SimpleNamespace(open_id="ou_operator"),
                message_id="om_target",
            ),
        )

        self.listener.do_p2_im_message_reaction_deleted_v1(data)

        self.assertEqual(len(recorder.calls), 2)
        self.assertEqual(recorder.calls[0]["metrics_delta"], {"reaction_given": -1})
        self.assertEqual(recorder.calls[1]["metrics_delta"], {"reaction_received": -1})

    def test_recalled_event_rolls_back_once(self):
        recorder = _RecordingStorage()
        self.listener.storage = recorder
        self.listener.get_cached_nickname = lambda uid: f"name-{uid}"
        self.listener.processed_events.clear()
        self.listener.recalled_messages_rolled_back.clear()

        self.listener.message_metric_snapshots.set(
            "om_recall_target",
            {
                "message_id": "om_recall_target",
                "chat_id": "oc_test_chat",
                "sender_id": "ou_sender",
                "sender_name": "name-ou_sender",
                "sender_metrics": {"message_count": 1, "char_count": 12, "topic_initiated": 1},
                "reply_target": {"user_id": "ou_reply_to", "user_name": "name-ou_reply_to"},
                "mention_targets": [{"user_id": "ou_mention", "user_name": "name-ou_mention"}],
            },
        )

        data1 = SimpleNamespace(
            header=SimpleNamespace(event_id="evt_recall_1", event_type="im.message.recalled_v1"),
            event=SimpleNamespace(message_id="om_recall_target", chat_id="oc_test_chat"),
        )
        data2 = SimpleNamespace(
            header=SimpleNamespace(event_id="evt_recall_2", event_type="im.message.recalled_v1"),
            event=SimpleNamespace(message_id="om_recall_target", chat_id="oc_test_chat"),
        )

        self.listener.do_p2_im_message_recalled_v1(data1)
        self.listener.do_p2_im_message_recalled_v1(data2)

        self.assertEqual(len(recorder.calls), 3)
        self.assertEqual(recorder.calls[0]["metrics_delta"], {"message_count": -1, "char_count": -12, "topic_initiated": -1})
        self.assertEqual(recorder.calls[1]["metrics_delta"], {"reply_received": -1})
        self.assertEqual(recorder.calls[2]["metrics_delta"], {"mention_received": -1})

    def test_force_flush_writes_pending_updates(self):
        recorder = _RecordingStorage()
        self.listener.storage = recorder
        self.listener.pending_updates.clear()
        self.listener.message_counter = 1

        self.listener.accumulate_metrics("ou_flush", "name-ou_flush", {"message_count": 1, "char_count": 5})
        self.listener.maybe_flush_pending_updates(force=True, reason="unit_test")

        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0]["user_id"], "ou_flush")
        self.assertEqual(recorder.calls[0]["metrics_delta"]["message_count"], 1)
        self.assertEqual(recorder.calls[0]["metrics_delta"]["char_count"], 5)
        self.assertEqual(self.listener.pending_updates, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
