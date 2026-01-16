# 部署前检查清单

**版本**: v1.0  
**更新时间**: 2026-01-16  
**适用场景**: 生产服务器部署

---

## ✅ 第一阶段：环境准备

### 1.1 服务器配置
- [ ] 服务器已准备就绪（Linux/Windows Server）
- [ ] Python 3.8+ 已安装
- [ ] 网络连接正常，可访问飞书API（`https://open.feishu.cn`）
- [ ] 磁盘空间充足（建议至少10GB可用空间）

### 1.2 环境变量配置
- [ ] 已创建`.env`文件（从`.env.example`复制）
- [ ] `APP_ID`已正确配置
- [ ] `APP_SECRET`已正确配置
- [ ] `CHAT_ID`已正确配置（目标群组ID）
- [ ] `BITABLE_APP_TOKEN`已正确配置
- [ ] `BITABLE_TABLE_ID`已正确配置

**可选功能配置**：
- [ ] 如需消息归档：`ARCHIVE_TABLE_ID`和`SUMMARY_TABLE_ID`已配置
- [ ] 如需Pin监控：`PIN_TABLE_ID`已配置
- [ ] `HEALTH_CHECK_PORT`已配置（默认8080）
- [ ] `MAX_RETRIES`已配置（默认10）
- [ ] `RETRY_DELAY`已配置（默认30秒）

---

## ✅ 第二阶段：飞书应用配置

### 2.1 基础权限（必需）
- [ ] `im:message` - 获取与发送单聊、群组消息
- [ ] `im:chat` - 获取群组信息
- [ ] `bitable:app` - 查看、评论、编辑和管理多维表格
- [ ] `contact:user.base:readonly` - 获取用户基本信息
- [ ] `contact:contact:readonly_as_app` - 以应用身份读取通讯录

### 2.2 高级功能权限（推荐）
- [ ] `im:message:readonly_as_app` - 获取群组中所有消息（Pin功能需要）
- [ ] `drive:drive` - 读取、编辑云空间中的文件（附件上传需要）
- [ ] `docx:document` - 查看、评论和导出文档
- [ ] `sheets:spreadsheet` - 查看、评论和导出电子表格

### 2.3 事件订阅
- [ ] 已启用**长连接模式**
- [ ] 已订阅`im.message.receive_v1`事件
- [ ] 已订阅`im.message.reaction.created_v1`事件
- [ ] （可选）已订阅`im.message.recalled_v1`事件
- [ ] （可选）已订阅`im.message.message_read_v1`事件

### 2.4 多维表格配置
- [ ] 用户活跃度统计表已创建，包含以下字段：
  - [ ] 用户ID（文本）
  - [ ] 用户名称（文本）
  - [ ] 人员（人员类型）
  - [ ] 统计周期（文本）
  - [ ] 发言次数（数字）
  - [ ] 发言字数（数字）
  - [ ] 被回复数（数字）
  - [ ] 单独被@次数（数字）
  - [ ] 发起话题数（数字）
  - [ ] 点赞数（数字）
  - [ ] 被点赞数（数字）
  - [ ] 活跃度分数（数字）
  - [ ] 更新时间（数字）

**如启用消息归档**：
- [ ] 消息归档表已创建
- [ ] 话题汇总表已创建

**如启用Pin监控**：
- [ ] Pin消息归档表已创建

---

## ✅ 第三阶段：代码部署

### 3.1 代码获取
- [ ] 代码已从Git仓库克隆到服务器
- [ ] 所有文件完整，无缺失

### 3.2 依赖安装
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

- [ ] 虚拟环境已创建
- [ ] 所有依赖包已安装成功
- [ ] 特别检查：Flask已安装（健康检查需要）

### 3.3 日志目录
- [ ] `logs/`目录已创建或程序可自动创建

---

## ✅ 第四阶段：本地测试

### 4.1 环境变量验证测试
```bash
python env_validator.py
```
- [ ] 所有必需环境变量验证通过
- [ ] 可选配置状态显示正确

### 4.2 健康检查测试
```bash
python health_monitor.py
```
- [ ] 健康检查服务启动成功
- [ ] 访问`http://localhost:8080/health`返回状态
- [ ] 访问`http://localhost:8080/status`返回详细信息

### 4.3 短期运行测试
```bash
python long_connection_listener.py
```
- [ ] 程序启动成功，无报错
- [ ] WebSocket连接成功
- [ ] 能够接收消息事件
- [ ] 数据正确写入Bitable
- [ ] 日志文件正常生成

**测试要点**：
- [ ] 发送测试消息，检查是否被捕获
- [ ] 检查Bitable中数据是否更新
- [ ] 检查日志中是否有错误
- [ ] 手动中断程序（Ctrl+C），检查是否优雅退出

### 4.4 长期稳定性测试
- [ ] 程序持续运行至少2-4小时无崩溃
- [ ] 日志轮转正常工作（如果文件达到10MB）
- [ ] 内存使用保持稳定，无泄漏迹象
- [ ] CPU使用率正常（应小于5%）

---

## ✅ 第五阶段：生产部署

### 5.1 后台运行配置

**方式A：systemd服务（推荐，Linux）**

创建服务文件：`/etc/systemd/system/feishu-monitor.service`
```ini
[Unit]
Description=Feishu Activity Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/feishu
Environment="PATH=/path/to/feishu/venv/bin"
ExecStart=/path/to/feishu/venv/bin/python long_connection_listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] 服务文件已创建
- [ ] 服务已启动：`systemctl start feishu-monitor`
- [ ] 服务已启用开机自启：`systemctl enable feishu-monitor`
- [ ] 服务状态正常：`systemctl status feishu-monitor`

**方式B：nohup后台运行（简单方案）**
```bash
nohup python long_connection_listener.py &gt; activity.log 2&gt;&1 &
```
- [ ] 程序已后台运行
- [ ] 进程ID已记录
- [ ] 日志正常输出到`activity.log`

### 5.2 健康检查验证
- [ ] 健康检查端口可从外部访问（如配置了防火墙需开放端口）
- [ ] `curl http://服务器IP:8080/health`返回正确状态
- [ ] 设置监控系统定期检查健康端点（可选）

---

## ✅ 第六阶段：监控和告警

### 6.1 系统监控
- [ ] 磁盘空间监控已配置（警告阈值：20%）
- [ ] 进程存活监控已配置
- [ ] 内存使用监控已配置（可选）
- [ ] CPU使用监控已配置（可选）

### 6.2 日志监控
- [ ] 日志轮转正常工作
- [ ] 错误日志告警已配置（可选）
- [ ] 定期检查日志目录大小

### 6.3 应用层监控
- [ ] 健康检查端点监控已配置
- [ ] 飞书API调用成功率监控（通过日志分析）
- [ ] Bitable写入成功率监控（通过日志分析）

---

## ✅ 第七阶段：应急预案

### 7.1 常见问题处理
- [ ] 已熟悉重启服务命令
- [ ] 已熟悉查看日志命令
- [ ] 已熟悉检查进程状态命令

**快速参考**：
```bash
# systemd方式
sudo systemctl restart feishu-monitor
sudo systemctl status feishu-monitor
sudo journalctl -u feishu-monitor -f

# nohup方式
kill <进程ID>
nohup python long_connection_listener.py &gt; activity.log 2&gt;&1 &
tail -f activity.log
```

### 7.2 备份策略
- [ ] `.env`文件已备份到安全位置
- [ ] 代码仓库有最新版本
- [ ] 多维表格数据已设置飞书自动备份（可选）

### 7.3 回滚计划
- [ ] 旧版本代码已保留
- [ ] 知道如何快速回滚到上一版本

---

## ✅ 第八阶段：文档和交接

### 8.1 文档完整性
- [ ] README.md已阅读并理解
- [ ] CODE_REVIEW_REPORT.md已阅读
- [ ] 部署文档已完成（本清单）

### 8.2 团队培训
- [ ] 运维人员已了解系统架构
- [ ] 运维人员已掌握重启流程
- [ ] 运维人员已掌握日志查看方法
- [ ] 运维人员知道健康检查端点

### 8.3 联系方式
- [ ] 技术负责人联系方式已记录
- [ ] 紧急情况处理流程已明确

---

## 📊 部署完成验证

**最终检查**（部署后24小时）：
- [ ] 系统持续运行24小时无崩溃
- [ ] 消息实时统计正常
- [ ] Bitable数据准确
- [ ] 日志无严重错误
- [ ] 健康检查端点持续返回healthy
- [ ] 内存和CPU使用正常
- [ ] 磁盘空间充足

---

## ✅ 签字确认

| 角色 | 姓名 | 日期 | 签名 |
|------|------|------|------|
| 开发负责人 | | | |
| 运维负责人 | | | |
| 项目经理 | | | |

---

**备注**：
1. 本清单中的所有项目都必须检查完成后才能正式部署
2. 如有任何项目无法完成，需记录原因并评估风险
3. 建议先在测试环境完整走一遍流程，再在生产环境部署
