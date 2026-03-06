# 项目进程记录（2026-03-06）

## 本次目标

- 将 Pin 汇总推送从“每天 09:00（昨日汇总）”调整为“每周一 09:00（上周汇总）”。

## 已完成

- 调度改造：
  - `pin_scheduler.py` 已改为 `schedule.every().monday.at("09:00")`。
  - 新增并启用周任务执行函数 `_run_weekly_pin_job()`。
  - `run_pin_audit_now()` / `run_pin_report_now()` 保持兼容名称，语义改为手动触发每周审计。
- 审计窗口改造：
  - `pin_daily_audit.py` 新增 `run_for_last_week()` 与 `_get_last_week_window()`。
  - 上周窗口定义为自然周：上周一 `00:00` 到本周一 `00:00`。
  - 保留 `run_for_yesterday()` 兼容接口（不走主调度链路）。
- 卡片文案改造：
  - 汇总标题改为“📌 上周加精（YYYY-MM-DD ~ YYYY-MM-DD）”。
  - 明细时间展示改为包含日期与时间，适配周汇总跨天场景。
- 运行文案与配置注释同步：
  - `long_connection_listener.py` 调度相关提示由“每日”改为“每周”。
  - `config/.env.example` 注释更新为“每周一 9:00 自动执行”。
- 核心文档同步：
  - 已更新 `README.md`、`docs/PIN_FEATURE_GUIDE.md`、`docs/USER_MANUAL.md`、`docs/ADMIN_MANUAL.md`、`docs/PROGRAM.md`、`docs/README.md`、`docs/FILE_INVENTORY.md`。

## 测试与验证

- 已更新测试：
  - `tests/test_pin_scheduler.py`
  - `tests/test_pin_daily_audit.py`
  - `tests/test_pin_audit_env.py`
- 执行命令：
  - `python -m pytest -q tests/test_pin_scheduler.py tests/test_pin_daily_audit.py tests/test_pin_audit_env.py`
- 结果：
  - `8 passed`

## 当前状态

- Pin 主链路已切换到“每周一 09:00 + 上周汇总”。
- 月度归档逻辑保持不变（每日 `02:00` 检查，仅每月 1 号执行）。
