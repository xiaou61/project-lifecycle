---
name: project-lifecycle
description: 管理需要跨会话追踪、多人协作或明显风险的开发工作，把需求、决策、任务和验证写入项目工件；边界清楚的小修复走短路径。
---

# Project Lifecycle

用项目工件保存可恢复的事实，用聊天推进当前动作。只在工作需要持久追踪、多人协作或有明显风险时创建完整工作项。

## 通用底线

- 开始或恢复受管理工作前，定位真实项目，读取适用的入口规则、`.agent/rules/always.md`、状态和当前工件；多仓库先从外层 `PROJECT-INDEX.md` 导航。
- 用户明确批准需求、方案、设计或任务后，才能跨对应门槛；“继续”“开始做”“执行 `WORK-*`”不单独批准。
- 只按已确认范围实施。目标、验收、公共行为、接口、数据、安全、部署或架构发生实质变化时，回到最早受影响工件并使下游失效。
- 未完成 `depends_on` 阻断实现和验收；`related_to` 只要求跨阶段前检查影响。
- 规则、批准、测试结果和长期记忆必须有真实依据；不覆盖用户资料，不提交凭据。

## 风险路由

| 工作 | 路径 |
| --- | --- |
| 单文件、低风险、边界明确 | 确认目标 -> 修改 -> 窄验证 |
| 需要持久追踪的普通功能 | `WORK-*` + `workflow: compact`，保留需求、任务和验证 |
| 新项目、跨模块、公共接口、数据、安全、迁移或架构 | 需求 -> 方案 -> 设计 -> 任务 -> 实现 -> 验证 |

详细的自然语言触发、恢复顺序、澄清边界、阶段门槛、关系和完成语义只维护在 `references/workflow.md`；各阶段写法按需读取对应参考文件。

## 参考入口

- `references/workflow.md`：唯一的恢复、批准、漂移、依赖、验证和完成协议。
- `references/requirements.md`、`proposal.md`、`design.md`、`tasks.md`、`testing.md`：阶段工件规则。
- `references/rules.md`、`relationships.md`、`specs.md`、`memory.md`、`core-history.md`：边界、关系和长期资料。
- `scripts/init_project.py`、`scripts/project_status.py`：幂等初始化与只读状态汇总。
