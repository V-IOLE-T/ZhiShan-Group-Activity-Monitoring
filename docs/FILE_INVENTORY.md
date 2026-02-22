# 项目文件清单（含用途）

更新时间：2026-02-22

## 1. 根目录核心代码

| 文件 | 作用 |
|---|---|
| `main.py` | 项目主入口，启动实时监听服务。 |
| `long_connection_listener.py` | 主运行流程：飞书长连接事件处理、统计更新、调度器启动。 |
| `auth.py` | 飞书 API 认证与 token 刷新。 |
| `collector.py` | 拉取群消息、用户信息（分页、限流）。 |
| `calculator.py` | 活跃度指标计算与消息文本解析。 |
| `storage.py` | 多维表格/文档写入层（活跃度、Pin归档、文档块写入）。 |
| `message_renderer.py` | 飞书消息内容转 Docx Block。 |
| `pin_daily_audit.py` | 每日 Pin 审计（每天 09:00 处理昨日新增 Pin）。 |
| `pin_scheduler.py` | 调度器（每日 Pin 审计 + 月度归档）。 |
| `monthly_archiver.py` | 月度归档任务（每月 1 号）。 |
| `pin_monitor.py` | 旧秒级 Pin 轮询实现（当前主流程已下线）。 |
| `pin_weekly_report.py` | Pin 周报脚本（兼容/辅助）。 |
| `health_monitor.py` | 健康检查接口与运行状态指标。 |
| `env_validator.py` | 环境变量校验。 |
| `rate_limiter.py` | API 限流器。 |
| `logger.py` | 日志初始化与轮转策略。 |
| `utils.py` | 通用工具（缓存、辅助函数）。 |
| `scripts` | 跨平台定时任务辅助脚本（Windows/Linux）。 |

## 2. 文档目录 `docs/`

| 文件 | 作用 |
|---|---|
| `docs/README.md` | 文档导航与快速入口。 |
| `docs/PROGRAM.md` | 当前功能全景与稳定性说明。 |
| `docs/USER_MANUAL.md` | 用户手册（星友视角）。 |
| `docs/ADMIN_MANUAL.md` | 管理者手册（运营动作）。 |
| `docs/PIN_FEATURE_GUIDE.md` | Pin 能力说明（当前为每日审计机制）。 |
| `docs/DEPLOYMENT_GUIDE.md` | 部署指南。 |
| `docs/DEVELOPMENT.md` | 开发指南。 |
| `docs/VISUALIZATION_GUIDE.md` | 可视化方案与说明。 |
| `docs/MANUAL_DESIGN.md` | 手册设计说明。 |
| `docs/FILE_INVENTORY.md` | 本文件：项目文件清单。 |

## 3. 单聊卡片模块 `reply_card/`

| 文件 | 作用 |
|---|---|
| `reply_card/__init__.py` | 模块入口。 |
| `reply_card/processor.py` | 单聊请求处理主流程。 |
| `reply_card/mcp_client.py` | MCP 调用封装。 |
| `reply_card/image_generator.py` | 图片生成流程。 |
| `reply_card/card_builder.py` | 卡片结构构建。 |
| `reply_card/card_style_generator.py` | 卡片样式生成。 |
| `reply_card/TEMPLATE_GUIDE.md` | 模板说明。 |
| `reply_card/TROUBLESHOOTING.md` | 故障排查。 |
| `reply_card/*.png` / `reply_card/*.jpg` | 素材图片。 |
| `reply_card/assets/` | 素材目录（可扩展）。 |

## 4. 配置与部署

| 文件 | 作用 |
|---|---|
| `config/.env` | 当前环境配置（含敏感信息）。 |
| `config/.env.example` | 环境变量模板。 |
| `config/.env.backup` | 配置备份。 |
| `deployment/Dockerfile` | 容器镜像构建。 |
| `deployment/docker-compose.yml` | 容器编排配置。 |
| `deployment/install_fonts.sh` | 部署字体安装脚本。 |
| `requirements.txt` | Python 依赖列表。 |

## 5. 测试目录 `tests/`

| 文件 | 作用 |
|---|---|
| `tests/__init__.py` | 测试包标识。 |
| `tests/test_auth.py` | 认证模块测试。 |
| `tests/test_calculator.py` | 指标计算测试。 |
| `tests/test_rate_limiter.py` | 限流逻辑测试。 |
| `tests/test_utils.py` | 工具函数测试。 |

## 6. 运行与工程辅助目录

| 路径 | 作用 |
|---|---|
| `logs/` | 运行日志输出目录。 |
| `__pycache__/` | Python 编译缓存。 |
| `venv/` | 虚拟环境目录。 |
| `github/` | 协作流程与编排文档（非业务运行核心）。 |
| `.claude/` | 本地 AI 命令与技能配置（非业务运行核心）。 |
| `openspec/` | 规范目录骨架。 |
| `.processed_daily_pins.txt` | 每日 Pin 审计去重记录。 |
| `README.md` | 项目根说明文档。 |
| `REORGANIZATION_GUIDE.md` | 重构说明。 |
| `.gitignore` / `.dockerignore` | 忽略规则。 |

## 7. 备注

- 线上主链路以 `main.py -> long_connection_listener.py -> pin_scheduler.py -> pin_daily_audit.py` 为准。  
- `pin_monitor.py`、`pin_weekly_report.py` 属于历史/兼容脚本，阅读时请以 `docs/PROGRAM.md` 和当前主链路为准。
