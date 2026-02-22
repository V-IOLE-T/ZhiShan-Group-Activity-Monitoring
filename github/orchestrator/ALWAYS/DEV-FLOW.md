# 开发流程

## Git Flow

```
Issue (GitHub) → 认领 → worktree 开发 → 测试 → PR → 合 main → 部署
```

---

## 完整开发周期

### 1. 从 Board 选取任务

```bash
# 从 RESOURCE-MAP.yml 读取 organization 信息
# 查看 Board
gh project item-list <NUMBER> --owner <ORG> --format json

# 选一个 Todo 的 Issue
gh issue view <number> -R <org>/<repo> --json title,body,comments
```

### 2. 认领 Issue

```bash
# 在 Issue 留 comment
gh issue comment <number> -R <org>/<repo> --body "开始开发，分支: feature/<number>-<name>"
```

### 3. 创建 Worktree

```bash
cd repos/<repo>
git fetch origin
git worktree add ../repos/<repo>-<feature> -b feature/<number>-<name> main
cd ../repos/<repo>-<feature>

# 安装依赖（按项目技术栈）
# pnpm install / go mod download / cargo fetch / pip install -r requirements.txt
```

### 4. 开发

在 worktree 中开发，提交代码：

```bash
# 检查命令（按项目技术栈）
# pnpm check / go vet ./... / cargo test / pytest
git add . && git commit -m "feat: xxx"
git push -u origin feature/<number>-<name>
```

### 5. 提交 PR

```bash
cd repos/<repo>-<feature>
gh pr create --base main --head feature/<number>-<name> --body "Closes #<number>"
```

在 Issue 留 comment 记录 PR 链接。

### 6. 合并

```bash
cd repos/<repo>
gh pr merge <PR号> --merge --delete-branch
```

Issue 通过 `Closes #<number>` 自动关闭。

### 7. 清理 Worktree

```bash
cd repos/<repo>
git worktree remove ../repos/<repo>-<feature>
git branch -D feature/<number>-<name>  # 如果本地分支还在
```

---

## 分支说明

| 分支 | 用途 |
|------|------|
| `main` | 稳定版本 |
| `dev` | 测试集成（可选） |
| `feature/<number>-*` | 功能开发 |
| `fix/<number>-*` | Bug 修复 |

---

## Commit 规范

格式：`<type>: <description>`

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 杂项 |

示例：
- `feat: add user authentication`
- `fix: resolve race condition in queue`
- `refactor: extract message parser`

---

## 部署（可选）

如果你有自动部署机制（如 webhook、CI/CD），在此描述：

```
触发条件: push 到 main
流程: pull → install → build → restart
验证: 查看部署日志
```

如果没有自动部署，删除此段即可。
