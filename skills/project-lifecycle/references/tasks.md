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
## 评审焦点
## 任务

### TASK-001 | pending | <任务名称>

- 对应：`REQ-001`、`AC-001`
- 依赖：无
- 新建/修改：`src/example.py`（新建写清为什么不能复用现有文件）
- 接口：消费 `Other.foo(a: A): B`；产出 `Thing.bar(): C`
- 测试：`tests/test_example.py::test_example`
- 步骤：
  1. <一个动作，一个可检查的结果>
  2. <一个动作，一个可检查的结果>
- 验证：`pytest tests/test_example.py -q` → 期望 1 passed

## 完成条件
```

## 接口块与步骤粒度

**接口块**写相邻任务之间真正会互用的符号：函数名、参数类型、返回类型，字面一致。它存在的理由是执行者不必去猜邻任务用了什么名字——`clearLayers()` 与 `clearFullLayers()` 是两个东西，不是笔误。纯内部实现细节不写进接口块，写进步骤。

**步骤**的判据是"一个动作 + 一个可检查的结果"：写失败测试、跑测试看它红、写最小实现、再跑、提交。`实现整个模块`、`处理各种情况`不是步骤，是把任务改了个说法。一个步骤写完后，执行者应该只有一种合理做法；如果需要两种，说明它该拆。

## 评审焦点

规格和设计里总有一些失败模式没有任何任务的测试会碰到：空输入、并发两次、权限边界、编码、超时、重复提交、边界值、部分失败。批准前列出它们，并给每条指定归属任务与测试：

```markdown
## 评审焦点

| 失败模式 | 归属任务 | 测试 |
| --- | --- | --- |
| 同一请求并发两次产生两条记录 | TASK-004 | `test_concurrent_create_is_idempotent` |
| 超长中文标题按字节截断 | TASK-006 | `test_long_cjk_title_truncates_on_char_boundary` |
```

每条都必须落到某个任务的测试里。写"无"时要说明为什么规格不暗示任何此类失败模式；空着不写等于跳过这项检查。

Use stable `TASK-*` identifiers when there is more than a trivial handful. Task state is `pending | in_progress | done | blocked`; artifact state remains `draft | approved | stale` in YAML frontmatter.

Each task should be small enough to implement and verify as one coherent change. State exact paths and existing symbol names when known, dependencies on earlier tasks, the requirements or acceptance criteria it serves, and at least one observable verification step. Do not include placeholder instructions such as "add suitable tests" or "handle edge cases" without naming the expected behavior.

优先把任务拆成纵向切片：每个任务穿过本次变更实际涉及的必要层（例如数据、接口、界面和测试），完成后能独立演示或验证用户可见行为，而不是按“先改完所有后端、再改完所有前端”做水平分层。每个任务显式列出真正会阻塞它的 `TASK-*`；没有实际依赖就写“无”，不要为了排序制造依赖。

如果无法纵向切片是因为一次机械重构会同时影响大量调用方，按“扩展旧接口 -> 分批迁移 -> 删除旧接口”的 expand-contract 顺序拆分，并保持旧形式在迁移期间可用。其他情况下，不要用一个“大重构”任务掩盖多个无法独立验证的交付结果。

在把任务计划标为 `approved` 前，向用户展示编号后的任务标题、阻塞关系和每项可独立交付的结果，并确认拆分粒度是否过粗、过细或需要合并。这个确认只校验执行计划，不重新决定已批准的产品范围。用户确认后用 `project-lifecycle.ps1 approve --artifact tasks` 盖章写入 `approved_by` 和 `approved_at`；只有该命令写签署字段（见 [workflow.md](workflow.md) 的“签署”）。同一轮确认涵盖多个阶段时用 `--artifact all` 一次签完，只留一条历史记录。

Do not duplicate detailed interface or data design from `design.md`; link to the relevant section. Do not turn every local edit into a separate task when one coherent task is easier to execute and review.

## 计划质量门（批准前自审）

任务计划服务执行，不是给读者看的规格说明。批准前逐项自检，发现问题就地改，不用再走一遍评审：

- **无占位**：`TBD`、`处理边界情况`、`补适当测试`、`按需完善` 这类不决定任何事的句子是缺口。要么写出预期行为、路径或断言，要么删掉这一条。
- **无替写代码**：如果签名和测试已经决定了函数体，把函数体抄进计划就是在写代码而不是写计划。真正的算法、协议细节、规格原文可以贴。
- **比例检查**：计划明显长于它所描述的代码，通常是任务被写得过细或被复制粘贴撑大；这时应该合并任务、删掉复述。
- **跨任务一致**：同一个符号、接口、字段名在不同任务里必须字面一致（`clearLayers()` 与 `clearFullLayers()` 是两个不同的东西，不是笔误）。
- **每条验收有归属**：每个 `AC-*` 至少出现在一个任务的“对应”里；没有归属的验收标准不会有人做，也不会有人验。
- **评审焦点有测试**：`## 评审焦点` 里每条失败模式都指到具体任务与测试名；只有现象没有测试名，等于没覆盖。
- **接口字面一致**：相邻任务的“接口”块里，同一个函数名、参数类型、返回类型写法必须完全一致。
- **状态可被脚本读到**：任务用 `### TASK-001 | pending | 名称`、带“状态”列的表格、或 `## T-01 名称` + 复选框小节之一。三种写法都能被状态查询解析；其他格式会让未完成的工作项显示成没有任务。

Keep `tasks.md` at `status: draft` until the user explicitly approves the implementation sequence. During implementation, update task state from actual execution. A local step discovered inside the approved design may be added with a short reason. If a task changes scope, public behavior, interfaces, owned data, security, migration, or architecture, stop and revise the earliest affected upstream artifact instead.
