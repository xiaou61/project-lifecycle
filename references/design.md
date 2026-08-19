# Design

Use this reference to turn an approved proposal into instructions that can be implemented without rediscovering material decisions.

## Grounding

- Read the approved requirements and proposal.
- Inspect the actual modules, interfaces, data stores, tests, and deployment configuration affected by the work.
- Reuse current architectural patterns unless the approved proposal deliberately changes them.
- Prefer exact repository paths and existing symbol names when known. Mark planned names as planned rather than describing them as existing.

## Design Artifact

Use only the sections that affect implementation:

```markdown
# <工作项>设计

## 系统上下文
## 组件与职责
## 请求或事件流程
## 接口与数据
## 持久化与迁移
## 失败处理与恢复
## 安全与权限
## 可观测性
## 实施顺序
## 测试策略
## 需求追踪
## 待决定事项
```

The design must identify boundaries that other modules rely on, state validation and failure behavior, and explain compatibility or migration where persisted data or public interfaces change. Diagrams are optional and should be used only when they clarify relationships that prose cannot express compactly.

Map design elements and planned tests back to requirements and acceptance criteria. Do not introduce speculative extension points or abstractions with only one foreseeable use.

Keep the design at `status: draft` until the user explicitly approves it. After approval, use `tasks.md` for exact execution order and file-level steps rather than expanding the design into a second checklist. During implementation, a material deviation returns the design to draft and makes the task plan and prior verification evidence `stale`; a local factual correction may be recorded without reopening approval.
