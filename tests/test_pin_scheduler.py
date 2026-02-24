from unittest.mock import Mock, patch

from pin_scheduler import PinReportScheduler


def test_scheduler_registers_daily_audit_at_0900():
    scheduler = PinReportScheduler(auth=None)
    scheduler.pin_auditor = Mock()
    scheduler.archiver = None

    job = Mock()
    job.day = job
    job.at.return_value = job
    job.do.return_value = job

    fake_thread = Mock()

    with patch("pin_scheduler.schedule.every", return_value=job), patch(
        "pin_scheduler.threading.Thread", return_value=fake_thread
    ):
        scheduler.start()

    job.at.assert_any_call("09:00")
    fake_thread.start.assert_called_once()
    scheduler.stop()
