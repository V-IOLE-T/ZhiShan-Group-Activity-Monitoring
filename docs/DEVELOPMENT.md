# 开发指南

## 开发环境设置

### 1. 安装开发依赖

```bash
# 安装所有开发工具
pip install -r requirements-dev.txt
```

### 2. 代码格式化工具

项目使用以下工具保持代码质量：

#### Black - 代码格式化
自动格式化Python代码，保持一致的代码风格。

```bash
# 格式化所有Python文件
black .

# 检查而不修改
black --check .
```

#### isort - 导入语句整理
自动整理和排序import语句。

```bash
# 整理导入语句
isort .

# 检查而不修改
isort --check-only .
```

#### flake8 - 代码检查
检查代码风格和潜在问题。

```bash
# 检查所有Python文件
flake8 .

# 检查特定文件
flake8 auth.py collector.py
```

### 3. 类型检查

使用mypy进行静态类型检查：

```bash
# 检查核心模块
mypy auth.py collector.py rate_limiter.py utils.py logger.py

# 检查所有文件
mypy .
```

### 4. 一键格式化

使用提供的脚本一次性运行所有工具：

```bash
python format_code.py
```

此脚本将依次运行：
1. isort - 整理导入
2. black - 格式化代码
3. flake8 - 检查代码质量
4. mypy - 类型检查（如果已安装）

## 运行测试

### 运行所有测试

```bash
# 使用unittest
python -m unittest discover tests -v

# 使用pytest（推荐）
pytest tests/ -v
```

### 运行特定测试文件

```bash
python -m unittest tests.test_auth -v
python -m unittest tests.test_calculator -v
python -m unittest tests.test_rate_limiter -v
python -m unittest tests.test_utils -v
```

### 测试覆盖率

```bash
# 运行测试并生成覆盖率报告
pytest tests/ --cov=. --cov-report=html

# 查看覆盖率报告
# 打开 htmlcov/index.html
```

## 代码质量标准

### 代码风格
- **行长度**: 最大100字符
- **缩进**: 4个空格
- **引号**: 优先使用双引号
- **导入**: 按标准库、第三方库、本地模块排序

### 命名规范
- **模块/文件**: `snake_case.py`
- **类**: `PascalCase`
- **函数/变量**: `snake_case`
- **常量**: `UPPER_CASE`

### 文档字符串
所有公共函数和类必须包含文档字符串：

```python
def function_name(param1: type1, param2: type2) -> return_type:
    """
    简短描述（一行）

    详细描述（可选）

    Args:
        param1: 参数1说明
        param2: 参数2说明

    Returns:
        返回值说明

    Raises:
        Exception: 异常说明

    Example:
        >>> result = function_name(1, 2)
        >>> print(result)
        3
    """
```

### 类型提示
核心模块必须包含完整的类型提示：

```python
from typing import List, Dict, Optional, Any

def process_data(items: List[Dict[str, Any]]) -> Optional[str]:
    """处理数据"""
    if not items:
        return None
    return str(items[0])
```

## Git提交规范

### 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type类型
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 重构
- `test`: 添加测试
- `chore`: 构建过程或辅助工具的变动

### 示例

```bash
feat(auth): 添加token自动刷新功能

- 检查token是否过期
- 提前5分钟自动刷新
- 添加force_refresh参数

Closes #123
```

## 开发工作流

### 1. 创建功能分支

```bash
git checkout -b feature/your-feature-name
```

### 2. 开发和测试

```bash
# 编写代码
# ...

# 运行格式化工具
python format_code.py

# 运行测试
pytest tests/ -v

# 提交代码
git add .
git commit -m "feat: 添加新功能"
```

### 3. 代码审查检查清单

提交PR前确保：
- [ ] 所有测试通过
- [ ] 代码已格式化（black, isort）
- [ ] flake8无错误
- [ ] 添加了类型提示
- [ ] 添加了文档字符串
- [ ] 更新了相关文档

## 常见问题

### Q: Black和flake8冲突怎么办？
A: `.flake8`配置文件已经忽略了与Black冲突的规则（E203, W503）

### Q: 如何跳过某行的flake8检查？
A: 在行尾添加 `# noqa: <error-code>`
```python
very_long_line_that_cannot_be_shortened = value  # noqa: E501
```

### Q: mypy报错说找不到模块怎么办？
A: 在`pyproject.toml`中设置 `ignore_missing_imports = true`，或安装类型存根包：
```bash
pip install types-requests
```

### Q: 如何只检查修改的文件？
A:
```bash
# 检查git暂存的文件
git diff --name-only --cached | grep "\.py$" | xargs black
git diff --name-only --cached | grep "\.py$" | xargs flake8
```

## 性能调优

### 分析代码性能

```bash
# 使用cProfile
python -m cProfile -o profile.stats long_connection_listener.py

# 使用line_profiler（需安装）
pip install line-profiler
kernprof -l -v your_script.py
```

## 调试技巧

### 1. 使用日志
```python
from logger import get_logger
logger = get_logger(__name__)

logger.debug("调试信息")
logger.info("一般信息")
logger.error("错误信息", exc_info=True)
```

### 2. 使用pdb调试器
```python
import pdb; pdb.set_trace()
```

### 3. 查看日志文件
```bash
# 实时查看日志
tail -f logs/feishu_20260115.log

# 仅查看错误
tail -f logs/feishu_error_20260115.log

# 搜索特定内容
grep "ERROR" logs/feishu_*.log
```

## 资源链接

- [Black 文档](https://black.readthedocs.io/)
- [isort 文档](https://pycqa.github.io/isort/)
- [flake8 文档](https://flake8.pycqa.org/)
- [mypy 文档](https://mypy.readthedocs.io/)
- [pytest 文档](https://docs.pytest.org/)
- [Python Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
