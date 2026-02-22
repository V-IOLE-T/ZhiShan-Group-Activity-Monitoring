# 工作协议

## GitHub 是唯一真相源

所有任务管理、上下文传递、进度跟踪都在 GitHub 上完成：

| 信息 | 载体 |
|------|------|
| 任务定义 | Issue body |
| 任务状态 | Project Board status |
| 工作进展 | Issue comment |
| 交接文档 | Issue comment（`## HANDOFF`） |
| 完成记录 | Issue 关闭 comment |

---

## 分支占领机制

分支 = 工作占领标识。

### 命名规范

```
feature/<issue-number>-<short-name>
fix/<issue-number>-<short-name>
```

示例：`feature/42-user-auth`

### 占领规则

| 状态 | 含义 |
|------|------|
| 分支存在 + Issue In Progress | 有人正在开发 |
| 分支存在 + Issue Todo | 之前有人开始过，可接手 |
| 无分支 + Issue Todo | 未开始，可认领 |
| PR merged + Issue Done | 已完成 |

### 接手流程

要接手一个已有分支的任务：

1. 读 Issue body + comments，获取完整上下文
2. 拉取分支到本地 worktree
3. 在 Issue 留 comment：`接手开发，从 <commit-sha> 继续`
4. 继续开发

---

## Issue 生命周期

```
创建 Issue → 加到 Project Board (Todo)
    ↓
认领 → 状态改 In Progress → 创建分支 → 留 comment
    ↓
开发中 → 关键进展留 comment
    ↓
会话中断 → 留 HANDOFF comment → push 分支
    ↓
接手 → 拉分支 → 读 HANDOFF → 继续
    ↓
完成 → PR → merge → Issue 自动关闭 → Done
```

---

## Issue Comment 规范

### 开工

```markdown
开始开发，分支: `feature/42-user-auth`
```

### 进展（按需）

```markdown
## 进展

- 完成了 xxx
- 遇到问题：yyy，决定 zzz
```

### 交接（会话结束未完成时，必须写）

```markdown
## HANDOFF

### 当前状态
- 已完成: xxx
- 进行中: yyy

### 分支
`feature/42-user-auth` @ <commit-sha>

### 下一步
1. 完成 zzz
2. 测试 aaa

### 注意事项
- bbb 需要特别处理
```

### 完成

```markdown
## 完成

PR #55 已提交/合并。

### 变更摘要
- 新增 xxx
- 修改 yyy

### 验证
- [x] 测试通过
- [x] 构建通过
```

---

## 上下文管理

Agent 的上下文窗口有限。大任务必然跨越多次会话，HANDOFF 机制保证跨会话零信息损失。

### 主动保存（推荐）

当你发现对话已经很长、接近上下文上限时，用户会要求你保存进度：

1. **push** 当前分支的所有 commit
2. 在 Issue 留 **`## HANDOFF`** comment（格式见上方）
3. 用户开新会话，说 "继续 #N"，Agent 从 HANDOFF 恢复

### Compress 后恢复

如果上下文已被自动压缩（compress），信息可能丢失：

1. 回退到 compress 之前的状态
2. 在回退后的完整上下文中执行 HANDOFF 流程
3. 开新会话，从 HANDOFF 恢复

HANDOFF 写入的是结构化的交接文档（已完成 / 进行中 / 下一步 / 注意事项），信息密度远高于 compress 后的残留上下文。

---

## Worktree 使用

**推荐使用 git worktree** 进行功能开发，不在主仓库上切分支：

```bash
# 创建 worktree
cd repos/<repo>
git worktree add ../repos/<repo>-<feature> -b feature/<number>-<name> main

# 接手已有分支
cd repos/<repo>
git fetch origin feature/<number>-<name>
git worktree add ../repos/<repo>-<feature> feature/<number>-<name>

# 清理
git worktree remove ../repos/<repo>-<feature>
```

原因：
- 主仓库可能有其他未提交的变更
- 多个任务并行时互不影响
- 保持主仓库干净

---

## Scope 控制

每个任务可以定义写入范围。在 Issue body 或单独的配置中指定：

```yaml
write:
  - src/auth/
  - src/middleware/

forbidden:
  - .env
```

- **只修改** `write` 允许的路径
- **超出范围**时询问用户，不要擅自修改
- `forbidden` 列表中的路径绝对不能写入

---

## 提交代码前

1. 在 worktree 目录运行检查命令（如 `pnpm check` / `go vet` / `cargo test`）
2. 确保功能完整，不要提交半成品
3. Commit message 遵循规范（见 DEV-FLOW.md）

---

## 文件通信原则

- 大段内容（代码、分析报告）写入文件或 Issue comment，不要塞进对话
- 引用文件路径而非复制内容
- 保护上下文窗口
