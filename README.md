# Project Lifecycle Skill

面向 Codex 的中文项目开发 Skill。它把需要持久追踪的需求、决策、任务和验证证据保存到目标项目的 `.agent/`，让跨会话恢复有事实依据，同时按工作风险缩短流程。

Skill 运行时入口是 `skills/project-lifecycle/SKILL.md`。详细协议按需从 `skills/project-lifecycle/references/` 读取；根目录 README 只做使用说明，不是运行时状态源。仓库的模块地图见 [VitePress 总索引](docs/reference/index.md)；项目理解型 HTML 的生成规则见 [`references/html.md`](skills/project-lifecycle/references/html.md)，实际文件只在用户同意后放入目标项目的 `.agent/html/`。

## 什么时候使用

| 工作类型 | 路径 | 必要资料 |
| --- | --- | --- |
| 单文件、低风险、边界清楚的小修复 | 确认目标 -> 修改 -> 窄验证 | 聊天记录和实际验证 |
| 需要跨会话追踪的普通功能 | `workflow: compact` | `requirements.md`、`tasks.md`、`testing/` |
| 跨模块、公共接口、数据、迁移、安全、部署或架构调整 | `workflow: full` | 需求 -> 方案 -> 设计 -> 任务 -> 实现 -> 验证 |

不要为了形式创建空白工件。详细的风险路由、恢复顺序、阶段门槛、关系、漂移和完成语义，以 [`references/workflow.md`](skills/project-lifecycle/references/workflow.md) 为唯一来源。

## 不变的边界

- 需求、方案、设计和任务计划必须分别获得明确批准后才能跨对应门槛。`继续`、`开始做`、`执行 WORK-*` 只表示继续已获授权的动作。
- 项目常驻规则未确认时，可以继续需求讨论、设计和不依赖未知规则的只读验证；实现、部署、迁移和数据变更仍然阻断。
- 未完成的 `depends_on` 阻断实现和验收；`related_to` 只要求跨阶段前检查影响。
- 目标、验收标准、公共行为、接口、数据、安全、部署或架构发生实质变化时，回到最早受影响的工件，并使下游工件失效。
- `passed` 只表示检查证据，不等于用户业务验收或发布。
- 不覆盖用户资料，不伪造批准、状态或测试结果，不提交密码、密钥和其他凭据。

多仓库工作区可以用外层 `.agent/PROJECT-INDEX.md` 导航，但工作项状态、规则和批准状态必须保留在真实源码仓库自己的 `.agent/` 中。

## 目标项目的资料

初始化后，项目只增加一个资料工作区，源码和可执行测试仍留在原目录：

```text
your-project/
  AGENTS.md                         项目级入口，可由初始化器创建
  AGENTS.override.md                用户自己的更高优先级规则（可选）
  .agent/
    README.md                       工作区说明
    INDEX.md                        按模块定位代码、规格、变更和理解材料
    rules/always.md                 用户确认后的项目常驻规范
    memory.md                       跨任务仍有效的长期记忆
    specs/                          当前共享事实、契约和边界
    changes/WORK-编号-中文名/       一次变更的需求、任务和验证
      requirements.md
      proposal.md                   full 模式
      design.md                     full 模式
      tasks.md
      testing/plan.md
      testing/report.md
    notes/ references/              决策理由和共享资料
    html/                            AI 生成的项目理解型 HTML
    history/ scripts/               Git 历史视图和确定性脚本
  src/                              项目原有源代码
  tests/                            项目原有可执行测试
```

`.agent/INDEX.md` 回答“这个模块的代码、规格、变更和理解材料在哪里”，只做导航，不复制阶段状态；`.agent/html/` 保存帮助理解项目的独立 HTML。`.agent/specs/` 回答“项目现在应该怎样工作”，`.agent/changes/` 回答“这次要改什么以及怎样证明改对”。`rules/always.md` 只放经用户确认、适用于多个任务的长期规则。

## Skill 包

```text
skills/project-lifecycle/
  SKILL.md                         运行时底线、风险路由和参考入口
  agents/openai.yaml               Codex UI 元数据
  references/workflow.md           唯一的详细执行与恢复协议
  references/rules.md              规则层级、优先级和恢复边界
  references/requirements.md       需求澄清和验收标准
  references/proposal.md           方案和取舍（full）
  references/design.md             组件、接口、数据流和失败行为（full）
  references/tasks.md              任务前置条件和执行拆分
  references/testing.md            验收矩阵、证据和剩余风险
  references/relationships.md      依赖和关联
  references/specs.md               稳定规格的写入边界
  references/memory.md              长期记忆的证据和失效规则
  references/core-history.md        Git 核心组件历史视图
  references/html.md                项目理解型 HTML 的同意与保存边界
  scripts/project-lifecycle.ps1    面向用户的统一命令入口
  scripts/init_project.py           幂等初始化器
  scripts/project_status.py         只读状态汇总器
  scripts/project_validate.py       严格校验器
  scripts/generate_core_history.py  Git 历史生成器
```

阶段工件的字段和写法见同名参考文件。不要在项目中另建 `.agent/current.md`、`state.json` 或手工状态索引。

## 快速开始

### 安装

在 Codex 中运行：

```text
使用 $skill-installer 从 https://github.com/xiaou61/project-lifecycle/tree/main/skills/project-lifecycle 安装 project-lifecycle。
```

也可以把仓库 checkout 到 Codex 支持的 Skill 发现目录。以当前 Codex 文档和 `$skill-installer` 输出为准，不要把某台机器的绝对路径写进项目规则。

### 初始化项目

```powershell
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" init "F:\我的项目"
```

初始化器是幂等的：缺少时创建资料目录、入口模板和历史脚本，保留已有 `AGENTS.md`、`.agent/`、源代码、测试和 Git 历史。它不会安装 Skill、猜测项目规则、移动旧目录、修改产品文件或创建空白工作项。

首次初始化后，Agent 先检查仓库并提出项目常驻规则草案；用户确认后才创建 `.agent/rules/always.md`。规则未确认前允许讨论和只读检查，但不能实现、部署、迁移或变更数据。

### 日常使用

直接使用自然语言即可：

```text
我想增加用户登录，先聊聊这个需求。
这版需求确认，继续给方案。
方案可以，结合当前代码做设计。
按这个计划开始做。
测试一下，告诉我哪些验收项过了。
当前任务状态是什么？
继续实施 WORK-003。
```

Agent 会主动给受管理需求分配不复用的中文名称和 `WORK-*` 编号。`WORK-*` 只用于跨会话定位，不代表批准。用户没有明确批准时，Agent 停在相应阶段并说明缺少的决定；局部事实修正如果不改变已批准范围，可以记录后继续。

### 查询状态

```powershell
# 当前非归档工作项
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" status "F:\我的项目"

# 只看可恢复上下文、阻塞、建议读取路径和接力提示
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" resume "F:\我的项目"

# 发布前严格检查工件和证据
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" validate "F:\我的项目"

# 按编号或中文名称查询
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" status "F:\我的项目" --work WORK-003
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" status "F:\我的项目" --work "用户登录"

# 包含归档资料
& "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1" status "F:\我的项目" --include-archive
```

状态查询返回当前阶段、工件状态、任务计数、依赖、关联、阻塞原因和下一步。`resume` 额外输出唯一可恢复工作项、建议读取路径和可复制接力句；JSON 顶层有稳定的 `schema_version` 和 `generated_at`，`git` 概览会标出脏工作区和归因状态。需要检查重复 `REQ-*`/`AC-*`/`TASK-*`、正式来源引用、结构化测试证据和项目规则时，使用 `project-lifecycle.ps1 validate`。外层工作区只返回导航提示，不承载 `WORK-*` 状态。

## 开发与发布

维护者提交前至少运行：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q skills/project-lifecycle/scripts
python -X utf8 skills/project-lifecycle/scripts/project_validate.py "F:\我的项目" --strict
git diff --check
```

版本按兼容性使用 `PATCH`、`MINOR`、`MAJOR`；在 `v1.0.0` 前使用 `v0.MINOR.PATCH`。不兼容的 `.agent/` 结构、状态语义或初始化行为必须在 Release 中说明迁移和回滚方式。

最小发布流程：

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

公开 tag 不移动、不覆盖。升级前先阅读 Release 说明；初始化器不是迁移器，存在不兼容结构时在独立分支手工迁移并重新验证。

## 边界

- 不替代 Git、CI、测试框架或项目管理平台。
- 不把聊天记录、临时错误或秘密写入长期记忆。
- 不凭提交信息猜测核心组件；核心组件必须由项目显式配置。
- 不自动批准、不自动扩大范围、不覆盖用户已有资料。
