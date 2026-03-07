from types import SimpleNamespace
from unittest.mock import Mock, patch

import pin_scheduler


def _build_job_mock():
    job = Mock()
    job.monday = job
    job.day = job
    job.at.return_value = job
    job.do.return_value = job
    return job


def test_scheduler_registers_jobs_and_runs_startup_archive_check():
    scheduler = pin_scheduler.PinReportScheduler(auth=None)
    scheduler.pin_auditor = Mock()
    scheduler.archiver = Mock()
    scheduler.archiver.archive_table_id = "tbl_archive"
    scheduler.archiver.should_run_startup_compensation.return_value = True

    weekly_job = _build_job_mock()
    archive_job = _build_job_mock()
    fake_thread = Mock()
    fake_schedule = SimpleNamespace(
        every=Mock(side_effect=[weekly_job, archive_job]),
        clear=Mock(),
        run_pending=Mock(),
        get_jobs=Mock(return_value=[]),
    )

    with patch.object(pin_scheduler, "schedule", fake_schedule), patch(
        "pin_scheduler.threading.Thread", return_value=fake_thread
    ):
        scheduler.start()
        scheduler.stop()

    weekly_job.at.assert_called_once_with("09:00")
    weekly_job.do.assert_called_once_with(scheduler._run_weekly_pin_job)
    archive_job.at.assert_called_once_with("02:00")
    archive_job.do.assert_called_once_with(scheduler._run_archive_job)
    scheduler.archiver.archive_and_clear.assert_called_once_with()
    fake_thread.start.assert_called_once()


def test_run_archive_job_calls_archiver_when_schedule_window_allows():
    scheduler = pin_scheduler.PinReportScheduler(auth=None)
    scheduler.archiver = Mock()
    scheduler.archiver.should_run_scheduled_archive.return_value = True

    scheduler._run_archive_job()

    scheduler.archiver.archive_and_clear.assert_called_once_with()


def test_run_archive_job_skips_when_outside_window():
    scheduler = pin_scheduler.PinReportScheduler(auth=None)
    scheduler.archiver = Mock()
    scheduler.archiver.should_run_scheduled_archive.return_value = False

    scheduler._run_archive_job()

    scheduler.archiver.archive_and_clear.assert_not_called()
