import sys
import types
from unittest.mock import Mock, patch

# pin_scheduler.py 依赖 schedule；当前解释器中若 schedule 模块不可用/不完整，则注入最小桩
if "schedule" in sys.modules and not hasattr(sys.modules["schedule"], "every"):
    del sys.modules["schedule"]
if "schedule" not in sys.modules:
    schedule_stub = types.ModuleType("schedule")
    schedule_stub.every = Mock()
    schedule_stub.clear = Mock()
    schedule_stub.run_pending = Mock()
    schedule_stub.get_jobs = Mock(return_value=[])
    sys.modules["schedule"] = schedule_stub

# pin_daily_audit.py 依赖 message_renderer；当前仓库缺失该文件时，测试环境注入最小桩实现
if "message_renderer" not in sys.modules:
    message_renderer_stub = types.ModuleType("message_renderer")

    class MessageToDocxConverter:  # noqa: N801
        def __init__(self, docx_storage):  # noqa: D401, ARG002
            self.docx_storage = docx_storage

        def convert(self, raw_content, message_id, doc_token, sender_name=None, send_time=None):  # noqa: ARG002
            return []

    message_renderer_stub.MessageToDocxConverter = MessageToDocxConverter
    sys.modules["message_renderer"] = message_renderer_stub

# pin_scheduler.py 依赖 storage；当前仓库缺失该文件时，测试环境注入最小桩实现
if "storage" not in sys.modules:
    stub_module = types.ModuleType("storage")

    class BitableStorage:  # noqa: N801
        def __init__(self, auth):  # noqa: D401, ARG002
            pass

    class DocxStorage:  # noqa: N801
        def __init__(self, auth):  # noqa: D401, ARG002
            pass

    stub_module.BitableStorage = BitableStorage
    stub_module.DocxStorage = DocxStorage
    sys.modules["storage"] = stub_module

from pin_scheduler import PinReportScheduler


def test_scheduler_registers_weekly_audit_on_monday_at_0900():
    scheduler = PinReportScheduler(auth=None)
    scheduler.pin_auditor = Mock()
    scheduler.archiver = None

    job = Mock()
    job.monday = job
    job.at.return_value = job
    job.do.return_value = job

    fake_thread = Mock()

    with patch("pin_scheduler.schedule.every", return_value=job), patch(
        "pin_scheduler.threading.Thread", return_value=fake_thread
    ):
        scheduler.start()

    job.at.assert_any_call("09:00")
    job.do.assert_any_call(scheduler._run_weekly_pin_job)
    fake_thread.start.assert_called_once()
    scheduler.stop()
