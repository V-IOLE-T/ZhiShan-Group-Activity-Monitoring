from env_validator import EnvironmentValidator


REQUIRED_ENV = {
    "APP_ID": "cli_test",
    "APP_SECRET": "secret",
    "CHAT_ID": "oc_test",
    "BITABLE_APP_TOKEN": "app_test",
    "BITABLE_TABLE_ID": "tbl_current",
}


def _set_required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_validate_announcement_tags_uses_default_when_unconfigured(monkeypatch, capsys):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("ANNOUNCEMENT_TAGS", raising=False)

    ok, warnings = EnvironmentValidator.validate(strict=False)
    output = capsys.readouterr().out

    assert ok is True
    assert "未配置，将使用默认值：公告,通知" in output
    assert "ANNOUNCEMENT_TAGS" not in " ".join(warnings)


def test_validate_announcement_tags_prints_configured_values(monkeypatch, capsys):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ANNOUNCEMENT_TAGS", "公告, 通知, 系统播报")

    EnvironmentValidator.validate(strict=False)
    output = capsys.readouterr().out

    assert "公告识别标签（可选覆盖，默认值：公告,通知）: 公告,通知,系统播报" in output


def test_validate_shows_archive_stats_and_hides_removed_legacy_keys(monkeypatch, capsys):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ARCHIVE_STATS_TABLE_ID", "tbl_archive_stats")
    monkeypatch.setenv("SUMMARY_TABLE_ID", "tbl_legacy_summary")
    monkeypatch.setenv("PIN_MONITOR_INTERVAL", "30")

    EnvironmentValidator.validate(strict=False)
    output = capsys.readouterr().out

    assert "月度归档历史表ID（启用月度归档时需要）: 已配置" in output
    assert "SUMMARY_TABLE_ID" not in output
    assert "PIN_MONITOR_INTERVAL" not in output
    assert "话题汇总表ID" not in output
    assert "Pin监控轮询间隔" not in output
