# Task Planning

Use this reference after the design is approved and before implementation begins. A task plan converts design decisions into an executable sequence; it does not choose product scope or architecture.

## Preconditions

- Read the approved `requirements.md`, `proposal.md`, and `design.md`.
- Inspect the current repository so paths, symbols, test locations, and commands are real rather than guessed.
- Return to the earliest affected artifact when a task would require new behavior or a material design decision.

## Task Artifact

Create `<artifact-root>/tasks.md` with only the detail needed to execute and verify the work:

```markdown
# <工作项>实施任务

## 依据
## 全局约束
## 任务

### TASK-001 | pending | <任务名称>

- 对应：`REQ-001`、`AC-001`
- 依赖：无
- 修改：`src/example.py`
- 测试：`tests/test_example.py`
- 步骤：
  1. <可执行步骤>
  2. <可执行步骤>
- 验证：`pytest tests/test_example.py -q`

## 完成条件
```

Use stable `TASK-*` identifiers when there is more than a trivial handful. Task state is `pending | in_progress | done | blocked`; artifact state remains `draft | approved | stale` in YAML frontmatter.

Each task should be small enough to implement and verify as one coherent change. State exact paths and existing symbol names when known, dependencies on earlier tasks, the requirements or acceptance criteria it serves, and at least one observable verification step. Do not include placeholder instructions such as "add suitable tests" or "handle edge cases" without naming the expected behavior.

Do not duplicate detailed interface or data design from `design.md`; link to the relevant section. Do not turn every local edit into a separate task when one coherent task is easier to execute and review.

Keep `tasks.md` at `status: draft` until the user explicitly approves the implementation sequence. During implementation, update task state from actual execution. A local step discovered inside the approved design may be added with a short reason. If a task changes scope, public behavior, interfaces, owned data, security, migration, or architecture, stop and revise the earliest affected upstream artifact instead.
