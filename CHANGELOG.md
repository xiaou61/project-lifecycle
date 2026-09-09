# 更新历史

本文件记录 `project-lifecycle` Skill 仓库本身的维护变更；目标项目的逐轮记录写在各自的 `.agent/history/updates.md`。Git 提交仍是可回滚事实源。

## 2026-09-09 · 文档预算、验证锚点与推送核验

- 类型：maintenance
- 变更：为状态恢复增加核心 Markdown 体积软警告；为验证报告增加 `verified_commit` 锚点状态；新增 `push-check` 与 `--record-push`，检测远端已推送但 `updates.md` 未记录的情况。
- 决策：文档超限只提示，不自动压缩或删除；远端查询只在显式 `push-check` 时执行；`updates.md` 仍是人工时间线，Git 远端仍是推送事实源。
- 依据：`skills/project-lifecycle/scripts/project_status.py`、`skills/project-lifecycle/scripts/update_history.py`、`skills/project-lifecycle/references/update-history.md`。
- 验证：44 个单元测试通过；Python 编译、Skill 校验、VitePress 构建和 `git diff --check` 通过；GitHub `origin/main` 已核对。
- 本地提交：实现提交 `2e2896b501f32b6c0818ad5f3eb98f49172f56ff`，发布记录提交 `a55ed6a872fab5bd049966378209ceb235fd09af`。
- 远端推送：实现、发布记录和元数据修订均已推送到 `origin/main` 并完成核对。
- 部署：`remote-45`，最新 release `/opt/project-lifecycle-docs/releases/20260909163928/dist`，服务 `project-lifecycle-docs.service` 已验证为 active。

## 2026-09-09 · 压缩后任务目标恢复包

- 类型：maintenance
- 变更：`resume --json` 从 `requirements.md` 提取 `goal`、`acceptance_criteria`、`constraints` 和 `goal_status`，文本恢复输出与接力提示同步带出；缺失目标或验收标准时返回明确警告。
- 决策：对话历史可以被压缩，当前任务状态继续以项目工件为唯一事实源；恢复包新增 `state_evidence`，明确工件状态、已记录测试、Git 快照和未知的源码同步，避免把过时 Markdown 当成实时代码状态；不新增数据库、向量存储或后台服务，长期 `.agent/memory.md` 不承担当前任务目标。
- 依据：`skills/project-lifecycle/scripts/project_status.py`、`skills/project-lifecycle/references/workflow.md`、`docs/guide/resume.md`。
- 验证：待本轮验证。
- 本地提交：待用户授权。
- 远端推送：未执行。

## 2026-09-09 14:10:00 +0800 · 发布三档模式与秒级更新历史

- 类型：maintenance
- 变更：提交 `976cf4b` 已推送到 GitHub `main`；VitePress 构建产物已部署到 `remote-45`。
- 决策：服务器使用独立 release 目录 `/opt/project-lifecycle-docs/releases/20260909135408/dist`，`current` 指向该目录并保留旧 release 供回滚。
- 依据：GitHub `origin/main`、远端 `project-lifecycle-docs.service` 和本地构建产物。
- 验证：远端服务 `active`；首页和 `/guide/qa` 返回 200；远端与本地 `index.html`、`guide/qa.html` SHA-256 一致。
- 本地提交：`976cf4b`。
- 远端推送：已推送 `origin/main`。
- 部署：已部署到 `remote-45`，监听 `4175`，入口为 `http://45.207.197.87:4175/`。

## 2026-09-09 13:47:43 +0800 · 更新历史时间精度

- 类型：maintenance
- 变更：`updates --record` 生成的更新标题精确到秒并带本地时区；列表解析继续兼容旧的纯日期标题。
- 决策：采用人类可读的 `YYYY-MM-DD HH:mm:ss ±HHMM`，不改写已有历史，也不引入独立时间服务。
- 依据：`skills/project-lifecycle/scripts/update_history.py`、`skills/project-lifecycle/references/update-history.md`。
- 验证：38 个单元测试通过；Python 脚本编译通过；Skill 校验通过；VitePress 构建通过；`git diff --check` 通过。
- 本地提交：待用户授权。
- 远端推送：未执行。

## 2026-09-09 · 三档风险模式

- 类型：maintenance
- 变更：增加 `lite`、`managed`、`strict` 三档风险路由；旧 `workflow: compact/full` 工件继续兼容推导；普通 `validate` 不再自动升级为严格校验。
- 决策：模式在开始时判断，风险上升只允许升级；严格模式增加必要工件和批准门槛，但不机械增加测试；冒烟测试仍仅按用户、项目规则或已批准计划执行。
- 依据：`skills/project-lifecycle/SKILL.md`、`skills/project-lifecycle/references/workflow.md`、`skills/project-lifecycle/references/testing.md`。
- 验证：37 个单元测试通过；Python 脚本编译通过；Skill 校验通过；VitePress 构建通过；`git diff --check` 通过。
- 本地提交：待用户授权。
- 远端推送：未执行。

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
