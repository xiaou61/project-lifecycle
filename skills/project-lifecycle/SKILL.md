---
name: project-lifecycle
description: 用户说“写需求”“把需求问透”“拆任务”“验收”“继续上次的活”“归档”“看项目状态”时使用；把需求、决策、任务和验证证据写入项目 `.agent/` 工件，支持需求访谈、PRD/任务拆解、审批签署和跨会话恢复。适用于需要跨会话追踪、多人协作或有明显风险的开发工作；一次性问答、纯代码审查、边界清楚的单文件小修复不创建完整工作项。
license: MIT
metadata:
  version: "0.0.5"
---

# Project Lifecycle

用项目工件保存可恢复的事实，用聊天推进当前动作。只在工作需要持久追踪、多人协作或有明显风险时创建完整工作项。

默认用简体中文写对话和本 Skill 创建的所有工件（含标题、说明、决策、测试计划、验证报告和历史标签）。保留代码标识符、路径、命令、需求/验收编号、机器可读状态值和 Git 提交原文；只有用户明确要求或目标仓库有强制语言规则时才切换。

命令入口：Windows 用 `scripts/project-lifecycle.ps1`，macOS/Linux 用 `scripts/project-lifecycle.sh`（或 `python3 scripts/project-lifecycle.py`）；三者共用 `project-lifecycle.py` 里的命令映射。下文用 `$lifecycle` 指代该入口，按当前宿主的 Skill 安装位置解析，例如 Codex 的 `$env:USERPROFILE\.codex\skills\`、ZCode 的 `$env:USERPROFILE\.agents\skills\`，不要把某个宿主的绝对路径写进项目规则。

每轮动作、恢复顺序、阶段门槛、签署、关系、规则优先级、规格与决策说明、归档统一维护在 `references/workflow.md`，本页不重复。查状态默认用 `$lifecycle brief <项目> --json`（约 3 KB）；要完整清单、签署历史或已归档项时用 `status`，要单工作项上下文用 `resume`。

## 三条不可让路的底线

- **不代签**：`approved_by`、`approved_at`、`approver_role`、`accepted_by`、`accepted_at` 只能由 `$lifecycle approve` 写入，模型不得自行填写——那等于替用户签字。
- **无证据不算通过**：没有新鲜跑过的命令输出，就不许声称完成；跳过的测试不等于通过；修缺陷要有“去掉修复会红”的反向验证。每条结论对应的命令与判据见 `references/testing.md` 的“完成前的硬门”。
- **范围变了回最早工件**：目标、验收、公共行为、接口、数据、安全、部署或架构发生实质变化时，回到最早受影响的工件并使下游失效，不能只在任务层面消化。

## 写任务

拆任务前读 `references/tasks.md` 的计划质量门，最常被跳过的三条：接口块要字面一致（相邻任务的函数名、参数、返回类型），评审焦点要把规格暗示的失败模式指到具体任务与测试名，步骤必须是“一个动作一个可检查结果”。

## 风险路由

| 工作 | 模式 | 必要记录 | 允许的验证 |
| --- | --- | --- | --- |
| 单文件、低风险、边界明确 | `lite` | 聊天，不创建完整 `WORK-*` | 能证明本次改动的最窄检查 |
| 需要持久追踪的普通功能 | `managed` | `WORK-*` + `workflow: compact`，保留需求、任务和验证 | 按验收矩阵执行，不因模式自动增加测试 |
| 新项目、跨模块、公共接口、数据、安全、迁移或架构 | `strict` | `WORK-*` + `workflow: full`，需求 -> 方案 -> 设计 -> 任务 -> 实现 -> 验证 | 最窄可信检查；严格校验是工件门槛，不等于更多测试 |

模式只在开始时判断一次；风险上升时只能升级，不能用低模式绕过公共接口、数据、安全、迁移、部署或架构门槛。判断依据写进 `requirements.md` 的 `mode_reason`，不要写成“因为重要”。

旧工件没有 `mode` 时按 `workflow: compact -> managed`、`workflow: full -> strict` 兼容推导。`lite` 不要求创建 `requirements.md`；若已经存在工作项，显式模式必须补 `mode_reason`。

## 触发与不触发

| 用户这么说 | 动作 |
| --- | --- |
| “帮我看看这个函数有没有 bug”“这段代码怎么走” | 直接读代码回答，不创建 `WORK-*` |
| “加个小校验，就在这个文件里” | 走 `lite`：确认目标 -> 改 -> 窄验证，不建完整工件 |
| “我有个想法，想加一个功能” | 进入需求讨论，稳定后创建 `requirements.md` |
| “按计划开始做”“实施 WORK-003” | 恢复状态、过门槛，**改代码前先问是否开 worktree**；用户同意才建，问过就不再重复 |
| “需求确认了，直接改完上线” | 批准需求不等于批准发布：实现后仍停在验证与部署门槛 |
| “把 WORK-003 标成通过” | 没有新鲜测试输出时拒绝，按 `references/testing.md` 的硬门要证据 |
| “这个需求变了，先不管旧方案” | 范围变了回最早受影响的工件，不能让下游悄悄失效 |

## 用户入口

`$lifecycle <init|status|brief|resume|validate|approve|archive>`，自然语言表达即可，入口与动作的对应关系见 `references/workflow.md` 的“用户如何触发”。不要要求普通用户直接运行 Python 文件。变更历史以 Git 提交为准，不维护按轮追加的项目历史文件。

三个不直观的点：`validate` 只有显式 `--strict` 才把兼容性警告视为失败；`approve` 是唯一能写签署字段的入口（`--artifact all` 一次签完已存在的阶段工件）；`archive` 只移动目录、不改内容。`compact`、`full` 和需求深挖是兼容字段或参考协议，不拆成会互相抢触发的重复 Skill。

## 参考入口

`requirements.md`、`tasks.md`、`testing.md`、`workflow.md` 顶部都有「常见借口与反驳」表，进入该阶段前先扫一眼。

- **协议**：`references/workflow.md` 是唯一的恢复、批准、漂移、依赖、规则层级、规格和决策说明、验证、完成协议；出现歧义、冲突或跨对话接力时读。
- **阶段工件**：`references/requirements.md`（含需求深挖）、`references/proposal.md`、`references/design.md`、`references/tasks.md`、`references/testing.md`。
- **示例**：`examples/managed-walkthrough.md`，首次执行或工件写法拿不准时读。
- **实现**：底层 Python 脚本属于 Skill 内部实现，一律通过 `$lifecycle` 调用，不从目标项目 `.agent/scripts/` 查找。
- **自检**：在 Skill 仓库根运行 `python -m unittest discover -s tests -p "test_*.py"`；至少 1 条测试，`Ran 0 tests` 不算通过。
