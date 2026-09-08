# Task Planning

Use this reference after the planning boundary is approved and before implementation begins. In `full` mode that boundary is the approved proposal and design; in `compact` mode it is the approved requirements. A task plan converts those decisions into an executable sequence; it does not choose product scope or architecture.

## Preconditions

- Read the approved `requirements.md`. In `full` mode also read the approved `proposal.md` and `design.md`; in `compact` mode the approved requirements and this task plan are the planning boundary.
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

优先把任务拆成纵向切片：每个任务穿过本次变更实际涉及的必要层（例如数据、接口、界面和测试），完成后能独立演示或验证用户可见行为，而不是按“先改完所有后端、再改完所有前端”做水平分层。每个任务显式列出真正会阻塞它的 `TASK-*`；没有实际依赖就写“无”，不要为了排序制造依赖。

如果无法纵向切片是因为一次机械重构会同时影响大量调用方，按“扩展旧接口 -> 分批迁移 -> 删除旧接口”的 expand-contract 顺序拆分，并保持旧形式在迁移期间可用。其他情况下，不要用一个“大重构”任务掩盖多个无法独立验证的交付结果。

在把任务计划标为 `approved` 前，向用户展示编号后的任务标题、阻塞关系和每项可独立交付的结果，并确认拆分粒度是否过粗、过细或需要合并。这个确认只校验执行计划，不重新决定已批准的产品范围。

Do not duplicate detailed interface or data design from `design.md`; link to the relevant section. Do not turn every local edit into a separate task when one coherent task is easier to execute and review.

Keep `tasks.md` at `status: draft` until the user explicitly approves the implementation sequence. During implementation, update task state from actual execution. A local step discovered inside the approved design may be added with a short reason. If a task changes scope, public behavior, interfaces, owned data, security, migration, or architecture, stop and revise the earliest affected upstream artifact instead.
