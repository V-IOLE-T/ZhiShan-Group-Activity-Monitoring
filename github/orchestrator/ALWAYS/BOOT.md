# Boot Sequence

## 首次启动

如果 `RESOURCE-MAP.yml` 内容为空（全部注释）：

1. 询问用户项目基本情况：仓库地址、技术栈、基础设施、部署方式
2. 根据用户描述生成 `RESOURCE-MAP.yml`
3. 根据项目特点调整 `AGENTS.md` 中的工作语言和风格
4. 继续正常启动流程

## 加载顺序

1. `orchestrator/ALWAYS/CORE.md` — 工作协议
2. `orchestrator/ALWAYS/DEV-FLOW.md` — 开发流程
3. `orchestrator/ALWAYS/RESOURCE-MAP.yml` — 资源索引
4. **连接 GitHub** — 读取 Project Board

## 启动流程

### 步骤 1：加载本地配置

读取 `orchestrator/ALWAYS/` 下的三个核心文件，理解工作规范和基础设施。

### 步骤 2：读取 Project Board

```bash
# 从 RESOURCE-MAP.yml 读取 organization.project_board.number 和 organization.name
gh project item-list <NUMBER> --owner <ORG> --format json
```

展示当前 Board 状态（Todo / In Progress / Done）。

### 步骤 3：用户指定任务

| 指令 | 操作 |
|------|------|
| "继续 #42" | 读 Issue → 读 comments → 检查/拉分支 → 继续开发 |
| "看看有什么" | 展示 Board，等用户选择 |
| "做新任务: xxx" | 创建 Issue → 加到 Board → 创建分支 → 开发 |

### 步骤 4：恢复上下文（继续已有任务时）

```bash
# 读 Issue 详情
gh issue view <number> -R <org>/<repo> --json title,body,comments,assignees,labels

# 检查关联分支
git branch -a | grep "feature/<number>"

# 如果分支存在，拉取并创建 worktree
git fetch origin feature/<number>-<name>
git worktree add repos/<repo>-<feature> feature/<number>-<name>
```

从 Issue comments 中找最近的 `## HANDOFF` 段落获取交接上下文。

### 步骤 5：输出状态

```
Issue: #42 - <title>
仓库: <repo>
状态: In Progress
分支: feature/42-<name>
上下文: [HANDOFF 摘要]
下一步: xxx
```

## 新任务启动流程

```bash
# 1. 创建 Issue
gh issue create -R <org>/<repo> --title "feat: xxx" --body "$(cat <<'EOF'
## 目标
...

## 背景
...

## 方案
...

## 范围
- 涉及仓库: <repo>
- 主要文件: src/xxx

## 验收标准
- [ ] 条件 1
- [ ] 条件 2
EOF
)"

# 2. 加到 Project Board
gh project item-add <NUMBER> --owner <ORG> --url <issue-url>

# 3. 创建分支 + worktree
cd repos/<repo>
git worktree add ../repos/<repo>-<feature> -b feature/<number>-<name> main

# 4. 在 Issue 留 comment
gh issue comment <number> -R <org>/<repo> --body "开始开发，分支: feature/<number>-<name>"
```
