import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from monthly_archiver import MonthlyArchiver


class DummyAuth:
    def get_headers(self):
        return {"Authorization": "Bearer test-token"}


def _build_archiver(monkeypatch, tmp_path):
    monkeypatch.setenv("BITABLE_APP_TOKEN", "app_test")
    monkeypatch.setenv("BITABLE_TABLE_ID", "tbl_current")
    monkeypatch.setenv("ARCHIVE_STATS_TABLE_ID", "tbl_archive")
    monkeypatch.setattr(MonthlyArchiver, "STATE_FILE", tmp_path / ".last_monthly_archive.txt")
    return MonthlyArchiver(DummyAuth())


def _make_record(record_id, user_id, period, user_name=None):
    return {
        "record_id": record_id,
        "fields": {
            "用户ID": user_id,
            "用户名称": user_name or f"user-{user_id}",
            "统计周期": period,
            "发言次数": 1,
        },
    }


def _build_local_tmp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp"
    base_dir.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(dir=base_dir))


def test_get_records_for_period_builds_period_filter(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    captured = {}

    def fake_search(table_id, payload):
        captured["table_id"] = table_id
        captured["payload"] = payload
        return []

    monkeypatch.setattr(archiver, "_search_records", fake_search)

    try:
        records = archiver.get_records_for_period("2026-02")

        assert records == []
        assert captured["table_id"] == "tbl_current"
        assert captured["payload"]["filter"]["conditions"] == [
            {"field_name": "统计周期", "operator": "is", "value": ["2026-02"]}
        ]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mark_period_completed_round_trip(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)

    try:
        assert archiver.get_last_completed_period() is None
        assert archiver.mark_period_completed("2026-02") is True
        assert archiver.get_last_completed_period() == "2026-02"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_should_run_startup_compensation_only_within_month_start_window(monkeypatch):
    archiver = MonthlyArchiver(DummyAuth())
    monkeypatch.setattr(archiver, "get_last_completed_period", lambda: None)

    assert archiver.should_run_startup_compensation(datetime(2026, 3, 2, 9, 0, 0)) is True
    assert archiver.should_run_startup_compensation(datetime(2026, 3, 4, 9, 0, 0)) is False


def test_should_run_startup_compensation_skips_when_period_already_completed(monkeypatch):
    archiver = MonthlyArchiver(DummyAuth())
    monkeypatch.setattr(archiver, "get_last_completed_period", lambda: "2026-02")

    assert archiver.should_run_startup_compensation(datetime(2026, 3, 2, 9, 0, 0)) is False


def test_should_run_scheduled_archive_on_first_day_and_compensation_window(monkeypatch):
    archiver = MonthlyArchiver(DummyAuth())
    monkeypatch.setattr(archiver, "get_last_completed_period", lambda: None)

    assert archiver.should_run_scheduled_archive(datetime(2026, 3, 1, 2, 0, 0)) is True
    assert archiver.should_run_scheduled_archive(datetime(2026, 3, 2, 2, 0, 0)) is True
    assert archiver.should_run_scheduled_archive(datetime(2026, 3, 4, 2, 0, 0)) is False


def test_archive_and_clear_skips_existing_records_and_marks_completed(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    records = [
        _make_record("rec_1", "ou_1", "2026-02", "Alice"),
        _make_record("rec_2", "ou_2", "2026-02", "Bob"),
    ]
    save_mock = Mock(return_value=True)
    delete_mock = Mock(return_value=True)
    mark_mock = Mock(return_value=True)

    monkeypatch.setattr(archiver, "get_records_for_period", lambda period: records)
    monkeypatch.setattr(
        archiver,
        "archive_record_exists",
        lambda user_id, period: user_id == "ou_1" and period == "2026-02",
    )
    monkeypatch.setattr(archiver, "save_to_archive", save_mock)
    monkeypatch.setattr(archiver, "delete_record", delete_mock)
    monkeypatch.setattr(archiver, "mark_period_completed", mark_mock)

    try:
        ok = archiver.archive_and_clear(target_period="2026-02")

        assert ok is True
        save_mock.assert_called_once_with(records[1]["fields"])
        assert delete_mock.call_count == 2
        mark_mock.assert_called_once_with("2026-02")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_archive_and_clear_does_not_delete_when_archive_step_fails(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    records = [
        _make_record("rec_1", "ou_1", "2026-02", "Alice"),
        _make_record("rec_2", "ou_2", "2026-02", "Bob"),
    ]
    delete_mock = Mock(return_value=True)
    mark_mock = Mock(return_value=True)

    monkeypatch.setattr(archiver, "get_records_for_period", lambda period: records)
    monkeypatch.setattr(archiver, "archive_record_exists", lambda user_id, period: False)
    monkeypatch.setattr(
        archiver,
        "save_to_archive",
        Mock(side_effect=[True, False]),
    )
    monkeypatch.setattr(archiver, "delete_record", delete_mock)
    monkeypatch.setattr(archiver, "mark_period_completed", mark_mock)

    try:
        ok = archiver.archive_and_clear(target_period="2026-02")

        assert ok is False
        delete_mock.assert_not_called()
        mark_mock.assert_not_called()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_archive_and_clear_does_not_mark_completed_when_delete_fails(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    records = [
        _make_record("rec_1", "ou_1", "2026-02", "Alice"),
        _make_record("rec_2", "ou_2", "2026-02", "Bob"),
    ]
    mark_mock = Mock(return_value=True)

    monkeypatch.setattr(archiver, "get_records_for_period", lambda period: records)
    monkeypatch.setattr(archiver, "archive_record_exists", lambda user_id, period: False)
    monkeypatch.setattr(archiver, "save_to_archive", Mock(return_value=True))
    monkeypatch.setattr(archiver, "delete_record", Mock(side_effect=[True, False]))
    monkeypatch.setattr(archiver, "mark_period_completed", mark_mock)

    try:
        ok = archiver.archive_and_clear(target_period="2026-02")

        assert ok is False
        mark_mock.assert_not_called()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_archive_and_clear_runs_compensation_even_when_period_marked_completed(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    records = [_make_record("rec_1", "ou_1", "2026-02", "Alice")]
    save_mock = Mock(return_value=True)
    delete_mock = Mock(return_value=True)
    mark_mock = Mock(return_value=True)

    monkeypatch.setattr(archiver, "get_last_completed_period", lambda: "2026-02")
    monkeypatch.setattr(archiver, "get_records_for_period", lambda period: records)
    monkeypatch.setattr(archiver, "archive_record_exists", lambda user_id, period: False)
    monkeypatch.setattr(archiver, "save_to_archive", save_mock)
    monkeypatch.setattr(archiver, "delete_record", delete_mock)
    monkeypatch.setattr(archiver, "mark_period_completed", mark_mock)

    try:
        ok = archiver.archive_and_clear(target_period="2026-02")

        assert ok is True
        save_mock.assert_called_once_with(records[0]["fields"])
        delete_mock.assert_called_once_with("rec_1")
        mark_mock.assert_called_once_with("2026-02")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_archive_and_clear_is_noop_when_no_records(monkeypatch):
    tmp_dir = _build_local_tmp_dir()
    archiver = _build_archiver(monkeypatch, tmp_dir)
    mark_mock = Mock(return_value=True)

    monkeypatch.setattr(archiver, "get_records_for_period", lambda period: [])
    monkeypatch.setattr(archiver, "mark_period_completed", mark_mock)

    try:
        ok = archiver.archive_and_clear(target_period="2026-02")

        assert ok is True
        mark_mock.assert_not_called()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
