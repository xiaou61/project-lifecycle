# Requirements Discovery

Use this reference while clarifying and recording what the user needs. Requirements describe desired behavior and constraints, not the implementation chosen to deliver them.

## Conversation

- Assign a concise Chinese work-item name when a managed requirement first appears, then preserve that name throughout the conversation and lifecycle artifacts. Read [relationships.md](relationships.md) to allocate its stable `WORK-*` identity and evaluate related requirements.
- When the user asks to investigate or interview the requirement before producing a PRD/Task, read [requirements-interview.md](requirements-interview.md) and use its optional deep-interview mode. It extends this conversation without changing the artifact or approval model.
- Begin from the user's stated outcome and inspect relevant repository context before asking questions the code can answer.
- Ask focused questions in small batches. Prioritize questions that change scope, user-visible behavior, data ownership, integrations, constraints, or acceptance.
- Reflect decisions back in concrete language and distinguish confirmed facts, assumptions, and open questions.
- Load `.agent/rules/always.md` before recording constraints. Put only this work item's stricter or additional constraints in `requirements.md`; do not duplicate every project rule or silently waive one. Follow [rules.md](rules.md) when a requested exception conflicts with a project `MUST`.
- Do not force the user through a generic questionnaire. Omit dimensions that do not matter to this work.
- In deep-interview mode, ask one focused question per round, reflect the answer into the artifact immediately, and stop only when the decision tree and final-confirmation conditions are closed.
- Ask only when the choice changes the goal, user-visible behavior, data ownership, external integration, public interface, acceptance, security, project rules, or deployment, and cannot be safely inferred from approved artifacts and repository patterns. Otherwise choose the existing pattern and record a material assumption.

## Requirements Artifact

在 `requirements.md` 的 frontmatter 中可选写 `workflow: compact`。`full`（默认）使用完整阶段；`compact` 适用于需要持久追踪但不需要独立 proposal/design 的普通功能，只要求已批准的需求、简短任务计划和验证资料。流程选择是当前工作项的约束，必须在需求确认时明确；不要为小修复创建工作项只是为了填写这个字段。

如果需求来自用户提供的 PRD、附件、Issue、外部链接或其他正式资料，在 frontmatter 中写 `source_coverage: required`，并增加一张来源覆盖表：

```markdown
## 来源覆盖

| 来源 | 锚点 | REQ | AC | 状态 |
| --- | --- | --- | --- | --- |
| PRD.md | 第 12-18 行 | REQ-001 | AC-001 | verified |
```

每一行都必须先读取来源、记录可复查的页码/行号/章节/链接锚点，再映射到至少一个 `REQ-*` 和 `AC-*`；`状态` 只有在来源已读取并核对后才写 `verified`。缺少表格、锚点、需求/验收映射或仍未验证时，状态检查器会把来源覆盖标为 `incomplete`，阻断实现、验证和完成结算。没有正式外部来源时不要为了形式填写该字段。

需要更强追踪时可使用 rich 格式：

```markdown
| 来源 | 类型 | 锚点 | 摘要 | REQ | AC | 适用路径 | 验证 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PRD.md | file | 第 12-18 行 | 登录成功后进入首页 | REQ-001 | AC-001 | src/auth/** | 逐行核对 | verified |
```

Write the shortest document that makes the work testable. Use these sections when relevant:

```markdown
# <工作项>需求

## 已确认事实
## 用户决定
## 实现选择
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

需求讨论中出现会反复使用、容易歧义或跨工作项共享的业务词汇时，可增加 `## 术语与边界`。只记录用户可见概念及其边界，不记录类名、函数名、数据库表名等实现细节。词语与现有项目术语冲突时，先指出冲突并让用户确认；只是当前任务的一次性措辞时，不要为了形式创建词汇表。

建议把事实、决定和选择分开记录：

- **已确认事实**：来自仓库、正式资料或已执行检查，可被复查；
- **用户决定**：由用户明确选择，影响范围、行为、数据、接口、安全或验收；
- **实现选择**：Agent 根据已批准边界和仓库模式做出的技术决定，不把无关细节反复交给用户；
- **待确认问题**：仍会改变需求的开放问题。

只有会改变交付边界的待确认问题阻断需求批准；实现选择必须记录理由，但不替代用户对产品范围的决定。

Give durable requirements stable identifiers such as `REQ-001` and acceptance criteria identifiers such as `AC-001` when there is more than a trivial handful. State acceptance criteria as observable outcomes. Avoid vague terms such as "fast", "easy", or "robust" unless the document defines what they mean.

For a new managed work item, create the initial `requirements.md` during the first discussion with its `work_id`, Chinese `work` name, the user's original outcome, known facts, and open questions. This is the current-phase artifact, not an empty scaffold. Use `depends_on` and `related_to` only as defined in [relationships.md](relationships.md), and explain each relation briefly under `## 关联工作项`.

Before approving requirements, search active work items for overlapping outcomes, acceptance criteria, shared contracts, data ownership, or interfaces. Merge requests that cannot be independently approved and accepted; use a hard dependency or soft relation only when they remain genuinely separate work items.

Keep the artifact at `status: draft` while a blocking question remains or until the user explicitly approves it. On approval, resolve or record every open question that affects scope and update the status and date.

If approved requirements later change materially, return them to `draft` and mark the existing proposal, design, task plan, and verification artifacts `stale` until they are reconciled. Preserve stable requirement and acceptance identifiers when their meaning remains the same; assign new identifiers instead of silently reusing an old identifier for a different obligation.
