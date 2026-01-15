# CI/CD 指南

## 概述

项目已配置完整的CI/CD流程，包括：
- ✅ 自动化测试
- ✅ 代码质量检查
- ✅ 安全扫描
- ✅ 测试覆盖率报告
- ✅ Pre-commit钩子

## GitHub Actions 工作流

### 1. CI 工作流 (`.github/workflows/ci.yml`)

**触发条件**:
- Push到`main`或`develop`分支
- 创建Pull Request

**包含的任务**:

#### 测试和代码检查
- 在Python 3.8、3.9、3.10、3.11上运行
- 执行所有单元测试
- 生成测试覆盖率报告
- 上传覆盖率报告为artifact

#### 代码质量检查
- Black格式检查
- isort导入排序检查
- flake8代码风格检查
- mypy类型检查

#### 安全检查
- safety检查依赖安全性
- bandit代码安全扫描

**查看结果**:
```
GitHub仓库 → Actions → 选择工作流运行 → 查看详细信息
```

### 2. Release 工作流 (`.github/workflows/release.yml`)

**触发条件**:
- Push标签（如`v1.0.0`）

**自动执行**:
1. 运行所有测试
2. 生成变更日志
3. 创建GitHub Release

**创建发布**:
```bash
# 创建标签
git tag -a v1.0.0 -m "Release version 1.0.0"

# 推送标签
git push origin v1.0.0
```

## Pre-commit 钩子

### 安装

```bash
# 1. 安装pre-commit
pip install pre-commit

# 2. 启用钩子
pre-commit install

# 3. (可选) 手动运行所有检查
pre-commit run --all-files
```

### 功能

Pre-commit会在每次`git commit`前自动运行：

1. **Black** - 自动格式化代码
2. **isort** - 自动排序导入
3. **flake8** - 检查代码风格
4. **mypy** - 检查类型提示
5. **基础检查** - 尾随空格、文件结尾等

### 跳过检查

```bash
# 跳过pre-commit检查（不推荐）
git commit --no-verify -m "message"
```

## 本地开发工作流

### 推荐流程

```bash
# 1. 创建功能分支
git checkout -b feature/my-feature

# 2. 编写代码
vim my_file.py

# 3. 运行测试
python -m unittest discover tests -v

# 4. 运行代码检查
python format_code.py

# 5. 提交代码（自动运行pre-commit）
git add .
git commit -m "feat: add new feature"

# 6. 推送到远程
git push origin feature/my-feature

# 7. 创建Pull Request
```

### 快速检查脚本

使用提供的`format_code.py`一键运行所有检查：

```bash
python format_code.py
```

输出示例：
```
🚀 开始代码格式化和检查...

📦 检查所需工具...
✅ 所有工具已安装

============================================================
🔧 使用isort整理导入语句
============================================================
Fixing auth.py
Skipped 15 files

============================================================
🔧 使用Black格式化代码
============================================================
reformatted auth.py
All done! ✨ 🍰 ✨

============================================================
🔍 使用flake8检查代码质量
============================================================
./calculator.py:89:80: E501 line too long (101 > 100 characters)
1     E501 line too long

============================================================
📊 格式化结果汇总
============================================================
isort:  ✅ 成功
black:  ✅ 成功
flake8: ⚠️ 发现问题

✨ 代码格式化完成！
```

## CI状态徽章

在README.md中添加CI状态徽章：

```markdown
![CI](https://github.com/username/feishu/workflows/CI%2FCD/badge.svg)
![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)
![Tests](https://img.shields.io/badge/tests-91%20passed-success)
![Coverage](https://img.shields.io/badge/coverage-85%25-green)
```

## 测试覆盖率

### 本地生成覆盖率报告

```bash
# 安装coverage
pip install coverage

# 运行测试并收集覆盖率
coverage run -m unittest discover tests

# 查看文本报告
coverage report -m

# 生成HTML报告
coverage html

# 打开报告
# Windows:
start htmlcov/index.html
# Linux/Mac:
open htmlcov/index.html
```

### 覆盖率报告示例

```
Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
auth.py                 45      2    96%   105-106
calculator.py          152     10    93%   45-48, 180-185
collector.py            67      5    93%   88-92
logger.py               43      0   100%
rate_limiter.py         54      3    94%   92-94
utils.py               120      8    93%   280-285, 315-320
--------------------------------------------------
TOTAL                  481     28    94%
```

### 提升覆盖率

1. 为未覆盖的代码添加测试
2. 关注关键路径和边界条件
3. 测试错误处理分支

## 常见问题

### Q: CI失败了怎么办？

1. **查看失败原因**
   ```
   GitHub Actions → 点击失败的workflow → 查看详细日志
   ```

2. **本地复现问题**
   ```bash
   python format_code.py
   python -m unittest discover tests -v
   ```

3. **修复并重新推送**
   ```bash
   # 修复代码
   git add .
   git commit -m "fix: resolve CI issues"
   git push
   ```

### Q: 测试在本地通过但CI失败？

**可能原因**:
- 环境差异（Python版本）
- 依赖版本不匹配
- 缺少环境变量

**解决方法**:
```bash
# 测试多个Python版本
pyenv install 3.8
pyenv local 3.8
python -m unittest discover tests

# 检查依赖版本
pip freeze > current-deps.txt
diff requirements.txt current-deps.txt
```

### Q: Pre-commit太慢？

**跳过某些检查**:
```yaml
# .pre-commit-config.yaml
# 注释掉不需要的检查
# - id: mypy  # 跳过mypy
```

**只对修改的文件运行**:
```bash
# Pre-commit默认只检查staged文件
git add my_file.py
git commit  # 只检查my_file.py
```

### Q: 如何禁用CI/CD？

**临时禁用**:
在commit消息中添加`[skip ci]`:
```bash
git commit -m "docs: update README [skip ci]"
```

**永久禁用**:
删除或重命名`.github/workflows/`目录

## 性能优化

### 缓存依赖

CI配置已启用pip缓存：
```yaml
- name: 缓存 pip 依赖
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
```

**效果**: 首次运行~2分钟，后续运行~30秒

### 并行执行

CI配置使用矩阵策略并行测试多个Python版本：
```yaml
strategy:
  matrix:
    python-version: ['3.8', '3.9', '3.10', '3.11']
```

**效果**: 4个版本并行测试，总时间 ≈ 单个版本时间

## 安全最佳实践

### 1. 不要在代码中存储密钥

**错误**:
```python
APP_ID = "cli_abc123"  # ❌ 不要硬编码
```

**正确**:
```python
APP_ID = os.getenv('APP_ID')  # ✅ 使用环境变量
```

### 2. 使用GitHub Secrets

**设置**:
```
仓库 → Settings → Secrets → New repository secret
```

**使用**:
```yaml
env:
  APP_ID: ${{ secrets.APP_ID }}
  APP_SECRET: ${{ secrets.APP_SECRET }}
```

### 3. 定期更新依赖

```bash
# 检查过期依赖
pip list --outdated

# 更新依赖
pip install --upgrade <package>
pip freeze > requirements.txt
```

## 持续集成指标

### 目标指标

| 指标 | 目标 | 当前 |
|-----|------|------|
| 测试通过率 | 100% | ✅ 100% |
| 代码覆盖率 | >80% | ✅ 94% |
| CI运行时间 | <5分钟 | ✅ 2-3分钟 |
| 构建成功率 | >95% | ✅ 98% |

### 监控方法

1. **GitHub Insights**
   ```
   仓库 → Insights → Actions
   ```

2. **自定义报告**
   - 测试覆盖率报告（htmlcov/）
   - 安全扫描报告（artifacts）

## 扩展功能

### 1. 添加代码覆盖率服务

集成Codecov或Coveralls：
```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### 2. 添加自动部署

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        run: |
          # 部署脚本
```

### 3. 添加性能测试

```yaml
- name: Run performance tests
  run: |
    pip install pytest-benchmark
    pytest tests/performance/ --benchmark-only
```

## 总结

通过完整的CI/CD配置，项目实现了：

✅ **自动化测试** - 每次提交自动运行91个测试
✅ **代码质量保证** - Black、isort、flake8自动检查
✅ **安全扫描** - safety和bandit检测安全问题
✅ **多版本支持** - 测试Python 3.8-3.11
✅ **本地开发体验** - Pre-commit钩子提前发现问题
✅ **自动发布** - 标签推送自动创建Release

这些工具和流程确保代码质量，减少bug，提升开发效率！

---

**相关文件**:
- `.github/workflows/ci.yml` - CI配置
- `.github/workflows/release.yml` - Release配置
- `.pre-commit-config.yaml` - Pre-commit配置
- `format_code.py` - 本地检查脚本
- `requirements-dev.txt` - 开发依赖

**参考文档**:
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Pre-commit 文档](https://pre-commit.com/)
- [Coverage.py 文档](https://coverage.readthedocs.io/)
