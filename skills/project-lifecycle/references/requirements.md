# Requirements Discovery

Use this reference while clarifying and recording what the user needs. Requirements describe desired behavior and constraints, not the implementation chosen to deliver them.

## Conversation

- Assign a concise Chinese work-item name when a managed requirement first appears, then preserve that name throughout the conversation and lifecycle artifacts. Read [relationships.md](relationships.md) to allocate its stable `WORK-*` identity and evaluate related requirements.
- Begin from the user's stated outcome and inspect relevant repository context before asking questions the code can answer.
- Ask focused questions in small batches. Prioritize questions that change scope, user-visible behavior, data ownership, integrations, constraints, or acceptance.
- Reflect decisions back in concrete language and distinguish confirmed facts, assumptions, and open questions.
- Load `.agent/rules/always.md` before recording constraints. Put only this work item's stricter or additional constraints in `requirements.md`; do not duplicate every project rule or silently waive one. Follow [rules.md](rules.md) when a requested exception conflicts with a project `MUST`.
- Do not force the user through a generic questionnaire. Omit dimensions that do not matter to this work.
- Ask only when the choice changes the goal, user-visible behavior, data ownership, external integration, public interface, acceptance, security, project rules, or deployment, and cannot be safely inferred from approved artifacts and repository patterns. Otherwise choose the existing pattern and record a material assumption.

## Requirements Artifact

在 `requirements.md` 的 frontmatter 中可选写 `workflow: compact`。`full`（默认）使用完整阶段；`compact` 适用于需要持久追踪但不需要独立 proposal/design 的普通功能，只要求已批准的需求、简短任务计划和验证资料。流程选择是当前工作项的约束，必须在需求确认时明确；不要为小修复创建工作项只是为了填写这个字段。

Write the shortest document that makes the work testable. Use these sections when relevant:

```markdown
# <工作项>需求

## 背景
## 目标
## 非目标
## 用户与工作流程
## 功能需求
## 质量要求
## 约束与依赖
## 关联工作项
## 验收标准
## 假设
## 待确认问题
```

Give durable requirements stable identifiers such as `REQ-001` and acceptance criteria identifiers such as `AC-001` when there is more than a trivial handful. State acceptance criteria as observable outcomes. Avoid vague terms such as "fast", "easy", or "robust" unless the document defines what they mean.

For a new managed work item, create the initial `requirements.md` during the first discussion with its `work_id`, Chinese `work` name, the user's original outcome, known facts, and open questions. This is the current-phase artifact, not an empty scaffold. Use `depends_on` and `related_to` only as defined in [relationships.md](relationships.md), and explain each relation briefly under `## 关联工作项`.

Before approving requirements, search active work items for overlapping outcomes, acceptance criteria, shared contracts, data ownership, or interfaces. Merge requests that cannot be independently approved and accepted; use a hard dependency or soft relation only when they remain genuinely separate work items.

Keep the artifact at `status: draft` while a blocking question remains or until the user explicitly approves it. On approval, resolve or record every open question that affects scope and update the status and date.

If approved requirements later change materially, return them to `draft` and mark the existing proposal, design, task plan, and verification artifacts `stale` until they are reconciled. Preserve stable requirement and acceptance identifiers when their meaning remains the same; assign new identifiers instead of silently reusing an old identifier for a different obligation.
