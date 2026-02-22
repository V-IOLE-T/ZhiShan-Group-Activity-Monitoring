# 飞书活跃度监测系统文档

本目录提供项目的功能、开发、部署与可视化说明。

## 文档导航

- [Program 文档](PROGRAM.md)
- [手册设计方案](MANUAL_DESIGN.md)
- [用户使用手册](USER_MANUAL.md)
- [管理者使用手册](ADMIN_MANUAL.md)
- [部署指南](DEPLOYMENT_GUIDE.md)
- [开发指南](DEVELOPMENT.md)
- [Pin 功能说明](PIN_FEATURE_GUIDE.md)
- [可视化指南](VISUALIZATION_GUIDE.md)

## 快速运行

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 准备配置
```bash
cp config/.env.example config/.env
```

3. 启动服务
```bash
python main.py
```

## API 优化

当前版本已具备以下 API 压降措施：

- 消息统计采用批量更新，避免每条消息都写表。
- 使用 LRU 缓存减少重复查询（事件去重、用户名缓存等）。
- 统一限流器控制 API 频率（默认 `20 次/60 秒`）。
- Pin 相关 API 调用改为每日 09:00 定时审计，不再使用秒级轮询。

说明：实际月度调用量受群消息活跃度、点赞事件、每日 Pin 审计命中情况等因素影响。
