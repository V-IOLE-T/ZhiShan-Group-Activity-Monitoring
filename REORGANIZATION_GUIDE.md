# 项目重组完成指南

## ✅ 已完成的重组

### 📁 新文件结构

```
feishu/
├── main.py                      # ✨ 新的主入口
├── long_connection_listener.py  # 原入口 (向后兼容)
│
├── 📂 docs/                     # 文档目录
│   ├── README.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── DEVELOPMENT.md
│   ├── PIN_FEATURE_GUIDE.md
│   └── VISUALIZATION_GUIDE.md
│
├── 📂 config/                   # 配置目录
│   ├── .env
│   ├── .env.example
│   └── .env.backup
│
├── 📂 deployment/               # 部署目录
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── install_fonts.sh
│
├── scripts                      # 脚本文件（当前为单文件）
│
├── 📂 tests/                    # 测试目录
├── 📂 logs/                     # 日志目录
├── 📂 reply_card/               # 回复卡片
│
└── *.py                         # 核心代码 (保持在根目录)
```

---

## 🚀 运行方式

### 方式一：使用新入口 (推荐)
```bash
python main.py
```

### 方式二：使用原入口 (向后兼容)
```bash
python long_connection_listener.py
```

**两种方式功能完全相同！**

---

## 📝 主要改动

### 1. 文档整理
- 所有 `.md` 文档移至 `docs/` 目录
- 根目录保留简化版 `README.md` 作为导航

### 2. 配置整理
- `.env` 等配置文件移至 `config/` 目录
- 代码自动检测并加载 `config/.env`
- 向后兼容：如果 `config/.env` 不存在，会尝试根目录

### 3. 部署文件整理
- `Dockerfile`, `docker-compose.yml`, `install_fonts.sh` 移至 `deployment/`

### 4. 脚本整理
- 辅助脚本保留为根目录单文件 `scripts`

### 5. 新增主入口
- 创建 `main.py` 作为统一入口
- 自动处理路径和环境变量

---

## ⚙️ 配置文件路径

**新路径**: `config/.env`

如果您的配置文件还在根目录，请移动：
```bash
# Windows
Move-Item .env config\

# Linux
mv .env config/
```

程序会自动检测两个位置，无需担心兼容性。

---

## 🧪 测试

### 1. 测试新入口
```bash
python main.py
```

### 2. 测试旧入口
```bash
python long_connection_listener.py
```

### 3. 测试 Pin 周报
```bash
python pin_weekly_report.py
```

---

## 📚 文档访问

所有文档现在位于 `docs/` 目录：

- [完整文档](docs/README.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [Pin 功能](docs/PIN_FEATURE_GUIDE.md)
- [可视化](docs/VISUALIZATION_GUIDE.md)

---

## 🔧 部署更新

### Docker 部署
```bash
docker compose -f deployment/docker-compose.yml up -d
```

### systemd 服务
更新服务文件中的启动命令：
```ini
# 新方式
ExecStart=/path/to/venv/bin/python /path/to/feishu/main.py

# 或保持原方式
ExecStart=/path/to/venv/bin/python /path/to/feishu/long_connection_listener.py
```

---

## ✅ 优势

1. **更清晰**: 文件分类明确，易于查找
2. **更专业**: 符合 Python 项目最佳实践
3. **向后兼容**: 旧的运行方式仍然有效
4. **易于维护**: 相关文件集中管理
5. **便于扩展**: 新功能有明确的归属

---

## ⚠️ 注意事项

1. **环境变量**: 确保 `config/.env` 文件存在且配置正确
2. **日志路径**: 日志仍在 `logs/` 目录
3. **Git**: 如果使用 Git，记得提交新的文件结构
4. **部署**: 更新服务器上的启动脚本路径

---

**重组完成时间**: 2026-01-19  
**向后兼容**: ✅ 完全兼容
