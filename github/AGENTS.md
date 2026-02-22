# AGENTS.md

此文件为 AI Coding Agent 在本工作区工作时提供指导。

---

## 工作语言与风格

- 简洁直接
- 代码注释清晰
- （Agent 首次启动时会根据用户偏好调整此段）

---

## 核心原则

**GitHub 是唯一真相源。**

- 任务定义、上下文、进展、交接 —— 全部在 GitHub Issue 上
- Project Board 是全局视图
- 分支是工作占领标识
- 本地 orchestrator 只提供启动引导和基础设施配置

---

## Boot Sequence

Agent 启动后：

1. **读取** `orchestrator/ALWAYS/BOOT.md`
2. **按指示加载**核心配置文件
3. **连接 GitHub**：读取 Project Board 获取任务列表
4. **用户指定任务**（如 "继续 #42" 或 "看看有什么"）
5. **输出**当前状态和下一步

如果用户未指定任务，展示 Board 现状并询问要做什么。

---

## 目录结构

```
your-project/
├── AGENTS.md                      # 本文件
├── orchestrator/
│   └── ALWAYS/                    # 核心配置（每次必读）
│       ├── BOOT.md                # 启动加载顺序
│       ├── CORE.md                # 工作协议
│       ├── DEV-FLOW.md            # 开发流程规范
│       ├── SUB-AGENT.md           # Sub-Agent 规范
│       └── RESOURCE-MAP.yml      # 资源索引
│
└── repos/                         # 代码仓库（可选，多仓库时使用）
```

---

## 快速命令

- "继续 #42" — 从 GitHub Issue 读上下文，拉分支，继续开发
- "看看有什么" — 展示 Project Board 当前状态
- "做新任务: xxx" — 创建 Issue，加到 Board，开始开发

---

## 状态来源

所有状态直接从 GitHub 读取：

| 信息 | 来源 |
|------|------|
| 任务列表 | `gh project item-list <NUMBER> --owner <ORG>` |
| 任务详情 | `gh issue view <number> -R <org>/<repo>` |
| 工作进展 | Issue comments |
| 关联分支 | `feature/<issue-number>-<short-name>` |
| 基础设施配置 | `orchestrator/ALWAYS/RESOURCE-MAP.yml` |

不在本地维护任何状态副本。
