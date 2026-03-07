# 项目进程记录（2026-03-07）

## 本次目标

- 清理已退役或未接线的运行时配置，避免启动状态继续误导。
- 保留公告专表能力，但明确 `ARCHIVE_TABLE_ID` 仅服务于公告归档。
- 收敛月度归档为“每月 1 号主执行 + 月初短窗口补偿”，兼顾可靠性与 API 配额。
- 为月度归档与遗留配置补齐自动化保障。

## 已完成

- 配置语义收敛：
  - `ARCHIVE_TABLE_ID` 启动文案已改为“公告归档表ID（启用公告专表写入时需要）”。
  - `ANNOUNCEMENT_TAGS` 已明确为“可选覆盖项”，未配置时默认使用 `公告,通知`。
  - `PIN_TABLE_ID` 启动文案已改为“Pin归档表ID（启用每周 Pin 审计写表时需要）”。
  - 新增 `ARCHIVE_STATS_TABLE_ID` 启动状态展示，用于提示月度归档历史表配置。
- 遗留配置清理：
  - 已从运行时校验、模板与主链路删除 `SUMMARY_TABLE_ID`。
  - 已从运行时校验、模板与主链路删除 `PIN_MONITOR_INTERVAL`。
  - 已移除 `storage.py` / `long_connection_listener.py` 中未接线的话题汇总死代码。
- 月度归档重构：
  - 月度归档只处理“上月统计周期”数据，不再全表搬运。
  - 历史表已存在同 `用户ID + 统计周期` 记录时，跳过写入但允许后续清理当前表旧记录。
  - 仅当归档确认完成后才删除当前表记录；任一归档或删除失败都会终止并等待补偿。
  - 新增 `.last_monthly_archive.txt`，用于记录最近一次完整成功的归档周期。
- 调度与补偿策略调整：
  - 主目标保持为每月 `1` 号 `02:00` 执行月度归档。
  - 若 `1` 号漏跑，仅在月初 `1-3` 号内补偿检查；`4` 号及以后不再自动补偿。
- 测试与工程保障：
  - 新增 `tests/test_monthly_archiver.py`、`tests/test_env_validator.py`。
  - 扩展 `tests/test_pin_scheduler.py`，覆盖 1 号主执行与月初补偿窗口。
  - 新增 `pytest.ini`，将收集范围锁定到 `tests/`，避免仓库根目录特殊文件影响全量 `pytest`。

## 关键行为（当前版本）

- 活跃值实时写入：
  - 当前月数据持续写入 `BITABLE_TABLE_ID`。
- 月度归档：
  - 归档源表：`BITABLE_TABLE_ID`
  - 归档目标表：`ARCHIVE_STATS_TABLE_ID`
  - 目标周期：始终为“上个月”
  - 主执行时间：每月 `1` 号 `02:00`
  - 补偿窗口：仅限当月 `1-3` 号
- 公告归档：
  - `ARCHIVE_TABLE_ID` 仅用于公告专表写入，不参与活跃值月度归档。

## 验证与验收

- 定向验证：
  - `python -m pytest -q tests/test_env_validator.py tests/test_monthly_archiver.py tests/test_pin_scheduler.py`
- 全量验证：
  - `python -m pytest -q`
- 结果：
  - 全量通过：`156 passed`
  - 仍有少量第三方依赖弃用警告（`lark_oapi` / `websockets` / `pkg_resources`），与本轮改造无关。

## 当前状态

- 配置表面已与当前业务链路对齐：
  - 公告专表保留
  - 话题汇总已移除
  - PinMonitor 轮询配置已退役
- 月度归档当前已满足：
  - 每月 `1` 号可执行
  - 漏跑可在月初短窗口补偿
  - 不会误归档本月新数据
  - 不会在失败时提前删除当前表记录
