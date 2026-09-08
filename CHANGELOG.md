# 更新历史

本文件记录 `project-lifecycle` Skill 仓库本身的维护变更；目标项目的逐轮记录写在各自的 `.agent/history/updates.md`。Git 提交仍是可回滚事实源。

## 2026-09-08 · 生命周期入口与更新记录

- 类型：maintenance
- 变更：修正状态/校验脚本的相对路径误用，统一通过 `project-lifecycle.ps1` 调用；初始化目标项目时增加 `.agent/history/updates.md`；补充每轮变更、决策、依据、验证和本地提交边界的规则与教程。
- 决策：`.agent/history/updates.md` 采用追加式人工可读时间线；Git 继续负责提交事实，`core-components.md` 继续负责确定性组件历史；本地 commit 是检查点，远端 push 必须用户明确授权。
- 依据：`skills/project-lifecycle/SKILL.md`、`skills/project-lifecycle/references/workflow.md`、`skills/project-lifecycle/references/update-history.md`。
- 验证：30 个单元测试通过；Skill 校验通过；Python 脚本编译通过；VitePress 构建通过。
- 本地提交：待用户授权。
- 远端推送：未执行。

## 2026-09-08 · 更新历史命令入口

- 类型：maintenance
- 变更：新增 `updates`、`record`、`checkpoint` 命令，分别用于查看更新历史、追加结构化记录和检查本地 Git 工作区；补充命令参考、README、总索引和回归测试。
- 决策：命令复用现有 `project-lifecycle.ps1`，只读检查和文本追加不自动提交；本地 commit 与远端 push 继续分离。
- 依据：`skills/project-lifecycle/references/update-history.md`、`skills/project-lifecycle/scripts/update_history.py`、`tests/test_project_status.py`。
- 验证：31 个单元测试通过；Skill 校验通过；Python 脚本编译通过；VitePress 构建通过。
- 本地提交：随本轮发布提交完成。
- 远端推送：用户已明确要求，随本轮提交执行。
