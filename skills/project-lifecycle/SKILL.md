---
name: project-lifecycle
description: 管理需要跨会话追踪、多人协作或明显风险的开发工作，把需求、决策、任务和验证写入项目工件；支持可选的需求深挖访谈，边界清楚的小修复走短路径。
---

# Project Lifecycle

用项目工件保存可恢复的事实，用聊天推进当前动作。只在工作需要持久追踪、多人协作或有明显风险时创建完整工作项。

## 通用底线

- 开始或恢复受管理工作前，定位真实项目，读取适用的入口规则、`.agent/rules/always.md`、状态和当前工件；多仓库先从外层 `PROJECT-INDEX.md` 导航。
- `.agent/INDEX.md` 只按模块导航到源码、规格、工作项和理解材料，不复制阶段或任务状态；项目理解型 HTML 仅在用户明确同意后放 `.agent/html/`。
- 每次实际修改后都要在 `.agent/history/updates.md` 追加变更、决策、依据、验证和提交边界；切换工作项或完成沉淀前必须留下本地检查点，远端 `push` 只能在用户明确授权后执行。
- 用户要求“问透需求”“详细调查需求”或明确要先访谈再出 PRD/Task 时，进入可选的需求深挖模式；普通需求和低风险修复不强制使用。
- 用户明确批准需求、方案、设计或任务后，才能跨对应门槛；“继续”“开始做”“执行 `WORK-*`”不单独批准。
- 只按已确认范围实施。目标、验收、公共行为、接口、数据、安全、部署或架构发生实质变化时，回到最早受影响工件并使下游失效。
- 未完成 `depends_on` 阻断实现和验收；`related_to` 只要求跨阶段前检查影响。
- 规则、批准、测试结果和长期记忆必须有真实依据；不覆盖用户资料，不提交凭据。
- 上下文压缩或换对话后，以 `resume --json` 返回的 `requirements.md` 目标、验收标准和约束恢复当前任务；聊天摘要和 `.agent/memory.md` 不能替代当前工作项事实。

## 风险路由

| 工作 | 路径 |
| --- | --- |
| 单文件、低风险、边界明确 | `lite`：确认目标 -> 修改 -> 窄验证，不创建完整 `WORK-*` |
| 需要持久追踪的普通功能 | `managed`：`WORK-*` + `workflow: compact`，保留需求、任务和验证 |
| 新项目、跨模块、公共接口、数据、安全、迁移或架构 | `strict`：`WORK-*` + `workflow: full`，需求 -> 方案 -> 设计 -> 任务 -> 实现 -> 验证 |

模式只在开始时判断一次；风险上升时只能升级，不能用低模式绕过公共接口、数据、安全、迁移、部署或架构门槛。`managed` 和 `strict` 的需求工件可记录：

```yaml
mode: managed
mode_reason: 需要跨对话继续，并涉及多个实现步骤
workflow: compact
```

旧工件没有 `mode` 时按 `workflow: compact -> managed`、`workflow: full -> strict` 兼容推导。`lite` 不要求创建 `requirements.md`；若已经存在工作项，显式模式必须补 `mode_reason`。

详细的自然语言触发、恢复顺序、澄清边界、阶段门槛、关系和完成语义只维护在 `references/workflow.md`；各阶段写法按需读取对应参考文件。

## 用户入口

本 Skill 对用户提供一个总入口和几个可组合动作：初始化、状态、恢复、校验、Git 历史视图、更新历史、记录更新、本地检查点和远端推送核验。用户可以直接用自然语言表达这些动作，也可以调用 `scripts/project-lifecycle.ps1 <init|status|resume|validate|history|updates|record|checkpoint|push-check>`；不要要求普通用户直接运行 Python 文件，入口与动作的对应关系见 `references/workflow.md` 的“用户如何触发”。

这些命令只是稳定的入口适配器，底层脚本属于 Skill 实现细节。`validate` 是普通校验，只有显式传入 `--strict` 才把兼容性警告视为失败。`lite`、`managed`、`strict` 是风险模式；`compact`、`full` 和需求深挖是兼容字段或参考协议，不拆成会互相抢触发的重复 Skill。

## 参考入口

- `references/workflow.md`：唯一的恢复、批准、漂移、依赖、验证和完成协议。
- `references/requirements-interview.md`：需求深挖的触发、决策树、逐轮提问、停止条件和 PRD/Task 输出边界。
- `references/tasks.md`：任务拆分、阻塞关系和可独立验证的纵向切片规则。
- `references/requirements.md`、`proposal.md`、`design.md`、`tasks.md`、`testing.md`：阶段工件规则。
- `references/html.md`：项目理解型 HTML 的用户同意、保存位置和事实边界。
- `references/rules.md`、`relationships.md`、`specs.md`、`memory.md`、`core-history.md`：边界、关系和长期资料。
- `references/update-history.md`：更新日志字段、本地提交检查点和远端推送边界。
- `scripts/init_project.py`、`scripts/project_status.py`：Skill 内部实现，负责幂等初始化（含项目总索引和 HTML 目录）与只读状态汇总；用户和 Agent 通过 `scripts/project-lifecycle.ps1 init/status/resume` 调用，不从目标项目 `.agent/scripts/` 查找这些文件。
- `scripts/project_validate.py`：Skill 内部的只读工件校验实现；通过 `scripts/project-lifecycle.ps1 validate` 调用，不要求普通用户直接运行 Python。
- `scripts/project-lifecycle.ps1`：面向用户的命令适配器，隐藏底层 Python 实现并转发 `init`、`status`、`resume`、`validate`、`history`、`updates`、`record`、`checkpoint`、`push-check`。
- `scripts/update_history.py`：更新历史的内部实现，负责读取、追加 `.agent/history/updates.md`，检查本地 Git 检查点，并按需核对远端推送记录；不要从目标项目 `.agent/scripts/` 查找这些文件。
