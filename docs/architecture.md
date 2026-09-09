# 技术架构与流转图

这张图把一次用户请求从入口到完成沉淀的真实路径串起来。点击节点可以查看该环节的输入、处理、输出、门槛和对应 Markdown；切换到“分层关系”可以理解聊天、Skill、项目工件、脚本和交付物之间的边界。

<LifecycleArchitecture />

## 先记住三条主线

1. **聊天是入口，不是事实库。** 用户用自然语言表达目标和批准，长期事实写进项目 `.agent/`。
2. **状态由工件和脚本推导。** 用户通过 `project-lifecycle.ps1 status/resume` 查询；适配器内部调用 `project_status.py` 负责“现在到哪一步、下一步是什么”，`project_validate.py` 负责“工件和证据是否合格”，需要把警告也视为失败时才使用 `--strict`。
3. **每一次跨阶段都有门槛。** “继续”是动作意图，不自动批准需求、方案、设计或任务；目标、接口、数据、安全或架构改变时回到最早受影响阶段。
4. **每一轮变化都有时间线。** `.agent/history/updates.md` 记录本轮变更、决策、依据、验证和提交边界；Git 提交保存可回滚事实，远端推送仍由用户单独授权。

## 推荐阅读路径

- 第一次使用：先看[开始使用](/guide/getting-started)，了解初始化和自然语言入口。
- 想知道完整阶段：看[全流程教程](/guide/full-workflow)。
- 想了解需求怎么问透：看[需求深挖访谈](/guide/requirements-interview)。
- 已经有 `WORK-*`：看[跨会话恢复与接力](/guide/resume)。
- 需要定位仓库文件：看[总索引](/reference/)。

## 为什么不是一堆重复 Skills

Superpowers 的做法是把开发方法拆成多个可组合 Skills，并把每个 Skill 的脚本留在包内，详见 [obra/superpowers](https://github.com/obra/superpowers)。我们借鉴它的“阶段可组合、实现内聚”原则，但保留一个 `project-lifecycle` 总 Skill：需求、批准、依赖、漂移和事实恢复必须共享同一套边界，拆成多个同名近似 Skills 反而会造成重复触发和状态分叉。

用户侧看到的是稳定动作入口：`init`、`status`、`resume`、`validate`、`history`；Agent 也可以直接用自然语言触发它们。PowerShell 适配器会在后台调用内部脚本，普通用户不需要直接使用 Python。

工作风险先路由到三档模式：`lite` 不创建完整工作项，`managed` 使用 `workflow: compact`，`strict` 使用 `workflow: full`。模式只影响必要的记录与阶段门槛，不把严格模式误解为无条件扩大测试范围。
