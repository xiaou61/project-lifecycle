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

## 2026-09-09 · 并发边界与使用 QA

- 类型：maintenance
- 变更：补充多对话并发与 Git Worktree 隔离规则；在 VitePress 增加 30 问 QA 页面，并接入导航和总索引；同步 README 与恢复教程的并发说明。
- 决策：明确 Skill 负责跨会话事实恢复、多个工作项选择和 Git 改动归因，但不承诺同一工作树的文件锁或自动合并；并行写入采用“一项工作、一个分支、一个 Worktree、一个写入对话”。
- 依据：`skills/project-lifecycle/references/workflow.md`、`docs/guide/resume.md`、`docs/guide/qa.md`。
- 验证：`npm run docs:build` 通过；31 个单元测试通过；Python 脚本编译通过；Skill 校验通过；`git diff --check` 通过。
- 本地提交：待用户授权。
- 远端推送：未执行。
- 部署：已发布到 `remote-45` 的 `project-lifecycle-docs.service`；当前目录为 `/opt/project-lifecycle-docs/releases/20260909104500/dist`，公网 `/guide/qa` 返回 200，页面哈希已核对。

## 2026-09-09 · 冒烟测试默认边界

- 类型：maintenance
- 变更：在测试规范、README、QA 和总索引中明确普通用户任务不默认执行冒烟测试，并将维护命令的“冒烟检查”改为入口/行为检查。
- 决策：只执行验收矩阵中最窄可信验证；冒烟测试仅在用户、项目常驻规则或已批准测试计划明确要求时执行；部署健康检查仍属于部署验证。
- 依据：`skills/project-lifecycle/references/testing.md`、`docs/guide/qa.md`。
- 验证：`npm run docs:build` 通过；31 个单元测试通过；Python 脚本编译通过；Skill 校验通过；`git diff --check` 通过；公网 `/guide/qa` 返回 200 且包含默认不执行冒烟测试的说明。
- 本地提交：待用户授权。
- 远端推送：未执行。
- 部署：已发布到 `remote-45` 的 `project-lifecycle-docs.service`；当前目录为 `/opt/project-lifecycle-docs/releases/20260909105439/dist`，页面哈希已与本地构建核对。

## v0.0.1 · 2026-09-09 · 首个可发布版本

- 类型：release
- 变更：将当前生命周期 Skill、VitePress 用户教程、30 问 QA、更新历史命令、并发边界和可选冒烟测试规则作为首个可发布基线。
- 决策：版本以不可移动的 Git tag `v0.0.1` 标识；后续按兼容性使用 `v0.MINOR.PATCH`，通过 GitHub 的分支、提交、tag 和 Release 流程发布。
- 依据：`README.md` 的版本与发布流程、`docs/guide/qa.md`、`skills/project-lifecycle/SKILL.md`。
- 验证：随发布提交执行完整回归、Skill 校验、Python 编译、VitePress 构建和 GitHub 远端 ref 校验。
- 本地提交：本次发布提交。
- 远端推送：随本次发布推送 `main` 和 `v0.0.1`。
