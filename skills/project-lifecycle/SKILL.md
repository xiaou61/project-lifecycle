---
name: project-lifecycle
description: 管理需要跨会话追踪、多人协作或明显风险的开发工作，把需求、决策、任务和验证写入项目工件；支持可选的需求深挖访谈，边界清楚的小修复走短路径。
---

# Project Lifecycle

用项目工件保存可恢复的事实，用聊天推进当前动作。只在工作需要持久追踪、多人协作或有明显风险时创建完整工作项。

## 每轮顺序

1. **确定项目**：多仓库先读外层 `PROJECT-INDEX.md`；再读目标项目的 `AGENTS.override.md`、`AGENTS.md`。
2. **恢复规范**：读 `.agent/rules/always.md`。缺失、草案或冲突时先提草案；实现、部署、迁移、数据变更要等确认。
3. **查状态**：默认用 `project-lifecycle.ps1 brief <项目> --json`。它只返回活动工作项、阻塞和下一步（约 3 KB）；要完整清单、签署历史或已归档项时用 `status`，要单工作项上下文用 `resume`。
4. **定位依据**：按编号或中文名选中工作项，读它的 `requirements.md`，再按当前阶段读已批准的上游工件。
5. **过门槛做一个动作**：核对规范、签署、硬依赖和关系影响，然后讨论、写工件、改代码、验证，或停在真实确认点。
6. **同步事实**：按实际结果更新工件与任务状态，追加 `.agent/history/updates.md`；需要接力时输出状态块。

## 三条不可让路的底线

- **不代签**：`approved_by`、`approved_at`、`approver_role`、`accepted_by`、`accepted_at` 只能由 `project-lifecycle.ps1 approve` 写入，模型不得自行填写——那等于替用户签字。
- **无证据不算通过**：没有新鲜跑过的命令输出，就不许声称完成；跳过的测试不等于通过；修缺陷要有"去掉修复会红"的反向验证。每条结论对应的命令与判据见 `references/testing.md` 的"完成前的硬门"。
- **范围变了回最早工件**：目标、验收、公共行为、接口、数据、安全、部署或架构发生实质变化时，回到最早受影响的工件并使下游失效，不能只在任务层面消化。

## 写任务的三个抓手

`references/tasks.md` 里有完整的计划质量门，其中三条最常被跳过：

- **接口块**：相邻任务会互用的函数名、参数类型、返回类型要字面写清，执行者不该去猜邻任务用了什么名字。
- **评审焦点**：列出规格暗示、但没有任务测试覆盖的失败模式（空输入、并发、权限、编码、超时、重复提交），每条指到具体任务与测试名。
- **一个步骤一个可检查结果**：`实现整个模块`不是步骤；写测试、跑红、写最小实现、再跑，才是。

## 风险路由

| 工作 | 路径 |
| --- | --- |
| 单文件、低风险、边界明确 | `lite`：确认目标 -> 修改 -> 窄验证，不创建完整 `WORK-*` |
| 需要持久追踪的普通功能 | `managed`：`WORK-*` + `workflow: compact`，保留需求、任务和验证 |
| 新项目、跨模块、公共接口、数据、安全、迁移或架构 | `strict`：`WORK-*` + `workflow: full`，需求 -> 方案 -> 设计 -> 任务 -> 实现 -> 验证 |

模式只在开始时判断一次；风险上升时只能升级，不能用低模式绕过公共接口、数据、安全、迁移、部署或架构门槛。判断依据写进 `requirements.md` 的 `mode_reason`，不要写成"因为重要"。`managed` 和 `strict` 的需求工件可记录：

```yaml
mode: managed
mode_reason: 需要跨对话继续，并涉及多个实现步骤
workflow: compact
```

旧工件没有 `mode` 时按 `workflow: compact -> managed`、`workflow: full -> strict` 兼容推导。`lite` 不要求创建 `requirements.md`；若已经存在工作项，显式模式必须补 `mode_reason`。

详细的自然语言触发、恢复顺序、澄清边界、阶段门槛、关系和完成语义只维护在 `references/workflow.md`；各阶段写法按需读取对应参考文件。出现歧义、冲突或跨对话接力时再打开它，不必每轮通读。

## 用户入口

一个总入口和几个可组合动作：初始化、状态、精简状态、恢复、校验、Git 历史视图、更新历史、记录更新、审批签署、归档、本地检查点和远端推送核验。用户可以直接用自然语言表达，也可以调用 `scripts/project-lifecycle.ps1 <init|status|brief|resume|validate|history|updates|record|approve|archive|checkpoint|push-check>`；不要要求普通用户直接运行 Python 文件，入口与动作的对应关系见 `references/workflow.md` 的"用户如何触发"。

这些命令只是稳定的入口适配器，底层脚本属于 Skill 实现细节。`validate` 是普通校验，只有显式传入 `--strict` 才把兼容性警告视为失败。`lite`、`managed`、`strict` 是风险模式；`compact`、`full` 和需求深挖是兼容字段或参考协议，不拆成会互相抢触发的重复 Skill。`approve` 是唯一把用户确认变成签署记录的入口；`approve --artifact all` 一次签完已存在的阶段工件并只写一条历史记录。`archive` 把已完成工作项移进 `changes/archive/`，默认只移动目录、不改内容。

## 参考入口

- `references/workflow.md`：唯一的恢复、批准、漂移、依赖、验证和完成协议；出现歧义、冲突或跨对话接力时读。
- `references/requirements-interview.md`：需求深挖的触发、决策树、逐轮提问、停止条件和 PRD/Task 输出边界。
- `references/tasks.md`：任务拆分、阻塞关系和可独立验证的纵向切片规则。
- `references/requirements.md`、`proposal.md`、`design.md`、`tasks.md`、`testing.md`：阶段工件规则。
- `references/html.md`：项目理解型 HTML 的用户同意、保存位置和事实边界。
- `references/rules.md`、`relationships.md`、`specs.md`、`memory.md`、`notes.md`、`core-history.md`：边界、关系、长期资料和决策理由。
- `references/update-history.md`：更新日志字段、本地提交检查点和远端推送边界。
- `scripts/init_project.py`、`scripts/project_status.py`：Skill 内部实现，负责幂等初始化（含项目总索引和 HTML 目录）与只读状态汇总；用户和 Agent 通过 `scripts/project-lifecycle.ps1 init/status/brief/resume` 调用，不从目标项目 `.agent/scripts/` 查找这些文件。
- `scripts/project_validate.py`：Skill 内部的只读工件校验实现；通过 `scripts/project-lifecycle.ps1 validate` 调用，不要求普通用户直接运行 Python。
- `scripts/project-lifecycle.ps1`：面向用户的命令适配器，隐藏底层 Python 实现并转发 `init`、`status`、`brief`、`resume`、`validate`、`history`、`updates`、`record`、`approve`、`archive`、`checkpoint`、`push-check`。
- `scripts/update_history.py`：更新历史的内部实现，负责读取、追加 `.agent/history/updates.md`、盖章签署、归档已完成工作项、检查本地 Git 检查点，并按需核对远端推送记录；不要从目标项目 `.agent/scripts/` 查找这些文件。
- `scripts/test_task_parsing.py`、`scripts/test_lifecycle_actions.py`：Skill 自身的自检（任务解析四种写法、批量签署与归档行为）。改动脚本后用 `python -m unittest discover -s <Skill 目录>/scripts -p "test_*.py"` 跑一遍。
