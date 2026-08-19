# Project Lifecycle Skill

一个面向 Codex 的中文项目开发生命周期 Skill。它把需求、提案、设计、实现、测试证据和长期记忆保存到仓库，而不是只留在一次聊天里，用明确的审批门槛控制项目漂移。

## Why：为什么需要它

Agent 很擅长快速写代码，但长期项目的主要风险通常不是“代码写不出来”，而是下面这些问题：

- 需求还没有说清楚，Agent 已经开始选择技术方案和修改代码。
- 几轮对话之后，最初的目标、非目标和关键约束逐渐丢失。
- 提案、设计、实现和测试各自看起来合理，放在一起却没有对齐。
- 实现遇到困难时，代码反过来悄悄改变需求，用户没有重新确认。
- “测试通过”没有对应到验收标准，也没有留下命令、环境和失败项。
- 新会话不知道旧项目为什么这样设计，只能重新猜测或依赖超长聊天记录。
- Git 能回答某个文件何时变化，却缺少按核心组件整理的可读视图。
- 每个项目都临时创建不同的文档目录，久而久之难以检索、复用和维护。

这个 Skill 的做法不是增加一套项目管理系统，而是把开发过程中的关键协议落到普通 Markdown、项目源代码、可执行测试和 Git 中：

```text
需求：我们到底要解决什么，怎样才算完成
  -> 提案：选择什么方向，为什么这样选
  -> 设计：在当前仓库里具体怎样实现
  -> 实现：按照已批准设计修改代码和测试
  -> 验证：用实际证据逐项证明验收标准
  -> 沉淀：只保留未来任务仍会用到的知识
```

小修复不需要被迫走完整流程。这个 Skill 主要用于重要功能、跨模块修改、长期项目和容易发生范围漂移的工作。

## 整体架构

系统分为三层：开源源码、本地 Skill、目标项目。它们是职责划分，不一定必须是三份物理副本。

```text
GitHub：xiaou61/project-lifecycle
  开发、版本管理、发布
              |
              | 安装、更新或直接 clone 到发现目录
              v
Codex Skill 发现目录
  project-lifecycle/
    SKILL.md
    agents/
    references/
    scripts/
              |
              | Codex 加载 $project-lifecycle
              v
被管理的目标项目
  AGENTS.md              项目级路由规则
  .agent/                需求、决策、验证、记忆和派生历史
  src/                   实际产品代码
  tests/                 实际可执行测试
  .git/                  代码与文档的版本事实源
      |
      `-> generate_core_history.py -> .agent/history/
```

三层的职责如下：

| 层 | 保存什么 | 不保存什么 |
| --- | --- | --- |
| GitHub 源码仓库 | 通用 Skill 指令、参考规范、脚本和发布版本 | 某个业务项目的需求与记忆 |
| Codex Skill 发现目录 | Codex 实际加载的 `project-lifecycle` | 目标项目的生命周期状态 |
| 目标项目 | `AGENTS.md`、`.agent/`、源代码、测试和 Git 历史 | Skill 本体的重复副本 |

如果把 GitHub 仓库直接 clone 到 Codex 的 Skill 发现目录，那么“源码仓库”和“本地 Skill”可以是同一个物理目录。必须保持分离的是目标项目：`.agent/` 只保存项目资料，不是 Skill 发现目录，也不应该包含整个 Skill。

Codex 官方当前支持在仓库或用户范围的 `.agents/skills/` 中发现 Skill；本环境内置的 `$skill-installer` 则安装到它配置的 `$CODEX_HOME/skills`，默认通常是 `~/.codex/skills`。优先使用当前环境的 `$skill-installer`，不要凭目录名称猜测是否已安装。参见 [OpenAI Skills 文档](https://learn.chatgpt.com/docs/build-skills)。

## 每个文件解决什么问题

### Skill 开源仓库

| 文件 | 解决的真实开发痛点 |
| --- | --- |
| `README.md` | 新用户容易混淆源码仓库、本地安装位置和目标项目；这里负责解释价值、架构、安装、操作和版本策略。 |
| `SKILL.md` | Agent 在不同会话中容易跳过阶段、自行批准或随意改变范围；这里定义共享流程、审批门槛、漂移控制和阶段路由。 |
| `agents/openai.yaml` | Skill 即使存在，也可能在界面中难以识别或不知道怎样开始；这里提供显示名称、简介和默认调用提示。 |
| `references/requirements.md` | 模糊需求容易直接变成代码；这里要求先明确目标、非目标、约束和可观察的验收标准。 |
| `references/proposal.md` | 团队容易把“要什么”“选什么方案”“怎样编码”混在一起；这里单独记录推荐方向、真实备选项和取舍。 |
| `references/design.md` | 实现阶段反复临场决定边界、接口、数据和失败行为；这里把已批准方案翻译成基于当前仓库的可实施设计。 |
| `references/testing.md` | 测试数量很多却不能证明需求完成，或只口头说“已通过”；这里把验收标准映射到实际命令、人工检查和剩余风险。 |
| `references/memory.md` | 长期知识散落在聊天和文档中，全部塞进一个文件又会变成噪音；这里定义可检索、可失效、有证据的记忆格式。 |
| `references/core-history.md` | 手工维护核心类变更日志容易过期，单看 `git log` 又不便按组件阅读；这里规定 Git 为事实源、Markdown 为可重建视图。 |
| `scripts/init_project.py` | 每个项目手工搭目录会产生不同结构，也可能误覆盖已有资料；这里用可重复、缺失才创建的方式初始化新项目或已有项目。 |
| `scripts/generate_core_history.py` | 人工抄写提交时间、作者和文件变化不可靠；这里从 Git 确定性生成核心组件历史，并支持过期检查。 |

`SKILL.md` 只保留所有阶段都需要知道的规则；`references/` 在进入对应阶段时才读取。这样既能约束流程，又不会每次把全部细节塞进 Agent 上下文。

### 初始化后的目标项目

| 文件或目录 | 解决的真实开发痛点 |
| --- | --- |
| `AGENTS.md` | Codex 进入仓库后不知道何时使用生命周期流程；它负责项目级路由，但不负责安装 Skill。 |
| `.agent/README.md` | 新会话或新成员不知道 `.agent/` 下各目录的职责；它是项目内的简短目录说明。 |
| `.agent/memory.md` | 跨会话的重要约束容易遗忘；它只保存当前仍有效、未来任务可检索的长期知识。 |
| `.agent/project/` | 项目整体启动时的需求、提案、设计和验证资料无处归档；这里保存项目级工作项。 |
| `.agent/features/<功能>/` | 多个功能的文档混在一起，状态和验收证据难以对应；每个重要功能使用独立资料根目录。 |
| `.agent/references/` | 业务规则、协议、外部规范散落在聊天或个人电脑；这里保存多个工作项共享的事实与来源。 |
| `.agent/notes/` | “为什么这样决定”只存在于某次讨论中；这里保存跨功能、长期有效的决策理由和取舍。 |
| `.agent/history/` | 核心组件的 Git 变化不方便日常查阅；这里保存可重新生成的历史视图。 |
| `.agent/scripts/` | 项目依赖某个确定性辅助动作，却要求 Agent 每次临时重写；这里保存项目本地使用的脚本副本。 |
| `requirements.md` | 固定目标、范围和验收标准，防止还未确认就进入方案。 |
| `proposal.md` | 固定已选择的实现方向和取舍，防止设计阶段重新发明方案。 |
| `design.md` | 固定组件、接口、数据流和测试策略，防止编码时发生未经批准的架构漂移。 |
| `testing/plan.md` | 在执行测试前明确验收覆盖、回归范围和已知缺口。 |
| `testing/report.md` | 保存实际执行结果，而不是把“应该能通过”当成完成证据。 |
| `.agent/core-components.json` | 明确哪些路径代表需要长期跟踪的核心组件，避免脚本凭提交信息猜测“什么最重要”。 |

`notes/` 和 `references/` 的区别是：`notes/` 回答“本项目为什么做出这个决定”，`references/` 回答“这个项目依赖哪些共享事实、规则或外部资料”。普通功能自己的方案理由留在 `proposal.md` 或 `design.md`，不要再重复写一份 Note。

## 安装到本地

仅仅把仓库放在任意目录并不等于安装。推荐在 Codex 中调用内置安装器：

```text
使用 $skill-installer 从 https://github.com/xiaou61/project-lifecycle 安装 project-lifecycle。
```

本环境也可以从 PowerShell 调用安装器脚本：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo xiaou61/project-lifecycle `
  --path . `
  --name project-lifecycle
```

这个具体路径属于本环境的 bundled installer，不应写进目标项目的 `AGENTS.md`。安装后如果当前会话尚未显示 `$project-lifecycle`，重新打开 Codex。

## 初始化新项目或已有项目

安装 Skill 后，在目标项目根目录调用：

```text
使用 $project-lifecycle 初始化当前项目，创建 .agent 工作区。
```

也可以直接运行已安装 Skill 中的初始化器：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\init_project.py" "F:\我的项目"
```

初始化器适用于空项目和正在开发的已有项目。它只完成下面这些操作：

- 目标项目缺少 `AGENTS.md` 时创建最小项目路由规则。
- 创建或补充 `.agent/`、`memory.md`、工作目录和辅助脚本。
- 保留已有 `AGENTS.md`、`AGENTS.override.md` 和 `.agent/` 文件。
- 不修改源代码、测试、依赖配置、分支、提交或 Git 历史。
- 可以重复执行；已有文件不会被覆盖。

如果已有 `AGENTS.md`，初始化器不会擅自追加规则，而会提示你确认其中是否已经包含生命周期路由。如果存在 `AGENTS.override.md`，它会优先于 `AGENTS.md` 生效。

生成的基本结构为：

```text
your-project/
  AGENTS.md
  .agent/
    README.md
    memory.md
    project/
    features/
    references/
    notes/
    history/
    scripts/
      generate_core_history.py
```

## 日常开发操作手册

### 1. 讨论需求

```text
使用 $project-lifecycle 开始“用户登录”功能。
先检查项目并和我讨论需求，不要设计，也不要写代码。
```

讨论稳定后：

```text
把结果写入 .agent/features/user-login/requirements.md，保持 draft。
```

### 2. 批准需求并生成提案

```text
我批准当前需求，请标记为 approved，并生成 proposal.md。不要编码。
```

Agent 不能根据“继续”或“生成下一份文档”自行推断批准。批准必须由用户明确表达。

### 3. 批准提案并生成设计

```text
我批准 proposal.md，请结合当前代码生成 design.md。不要实现。
```

### 4. 批准设计并实现

```text
我批准 design.md。请按批准文档实现并添加测试；如果需要实质性偏离，先停止并告诉我。
```

源代码和可执行测试写入项目原有目录，不写入 `.agent/`。

### 5. 测试和验证

```text
进入测试与验证阶段。生成 testing/plan.md，运行相关测试，并生成 testing/report.md。
```

最终资料形态：

```text
.agent/features/user-login/
  requirements.md
  proposal.md
  design.md
  testing/
    plan.md
    report.md
```

### 6. 最终对齐审计

```text
使用 $project-lifecycle 执行最终对齐审计，检查需求、提案、设计、代码、测试和验证报告是否一致。
```

只有文档、代码和证据真正一致时才算完成；文件状态写着 `approved` 或 `passed` 本身不是证明。

## 防止项目漂移

上游发生实质变化时，回到最早受影响的文档：

```text
修改最早受影响的文档并回到 draft
  -> 受影响的下游文档标记 stale
  -> 用户重新批准
  -> 依次更新下游文档
  -> 重新实现和验证
```

实质变化包括目标、非目标、验收标准、公共行为、接口、数据、安全、迁移或架构变化。局部变量改名或等价 API 调整通常不需要重走审批。

不要创建 `requirements-v2-final.md`、`design-final-final.md` 一类文件来表示修订。文件名保持稳定，当前有效状态写在文档 frontmatter 中，所有历史版本由 Git 保存。

## 项目长期记忆

`.agent/memory.md` 保存当前仍有效、会影响后续多个任务的项目知识。它不是聊天记录、任务日志或待办清单。

记忆条目格式：

```markdown
## MEM-001 | active | constraint

- 摘要：所有公开 API 的时间字段统一使用 UTC ISO 8601。
- 标签：`api` `time` `serialization`
- 范围：`src/api/`
- 依据：`.agent/notes/api-time-format.md`
- 记录：2026-08-19
- 复核：2026-08-19
- 失效条件：公开 API 版本策略发生变化。
```

快速列出全部记忆：

```sh
rg -n "^## MEM-" .agent/memory.md
```

按模块、标签或关键词搜索：

```sh
rg -n -i -C 6 "auth|session|security" .agent/memory.md
```

任务进度、临时错误、聊天摘要、未经证实的猜测和密钥不得写入长期记忆。记忆与当前代码、已批准文档、测试或 Git 冲突时，先核对事实源，再把记忆标记为 `stale` 或替换。

## 核心组件历史

在 `.agent/core-components.json` 中显式声明核心组件：

```json
{
  "units": [
    {
      "id": "user-service",
      "name": "用户服务",
      "paths": ["src/services/user-service.ts"]
    }
  ]
}
```

生成历史：

```sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

检查报告是否过期：

```sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md \
  --check
```

Git 是提交时间、作者、哈希和文件变化的唯一事实源；生成的 Markdown 只是可重建视图。可以显式配置 `post-commit` hook 更新视图，但 hook 不应自动创建第二个提交。

## 版本策略

这里有两类“版本”，不要混在一起：

1. `project-lifecycle` Skill 的发布版本，用 Git tag 和 Semantic Versioning 管理。
2. 目标项目需求、提案和设计的修订版本，用稳定文件名、文档状态和 Git 历史管理。

### Skill 发布版本

正式发布使用 `vMAJOR.MINOR.PATCH` 标签，例如 `v1.2.3`：

| 版本变化 | 什么时候使用 | 示例 |
| --- | --- | --- |
| `PATCH` | 文档修正、兼容性错误修复、输出不变的脚本修复 | `v1.2.3 -> v1.2.4` |
| `MINOR` | 新增向后兼容的阶段、参考规范、可选能力或初始化内容 | `v1.2.3 -> v1.3.0` |
| `MAJOR` | 不兼容地修改 `.agent/` 结构、文档格式、状态语义、审批规则或初始化行为 | `v1.2.3 -> v2.0.0` |

在 `v1.0.0` 之前使用 `v0.MINOR.PATCH`。`0.x` 阶段仍可能在 `MINOR` 中出现结构调整，但发布说明必须明确迁移影响；进入 `v1.0.0` 后严格按上表处理不兼容变更。

尚未创建 tag 的 `main` 只是开发版本，不应被宣称为某个正式版本。Git tag 是 Skill 版本的事实源，不在多个文件里重复维护容易漂移的版本号。

### 每次发布怎么做

每个版本按同一套最小流程发布：

1. 根据兼容性判断 `PATCH`、`MINOR` 或 `MAJOR`，不要按改动文件数量决定版本。
2. 更新 README；存在不兼容变化时，必须写清受影响文件、迁移步骤和回滚方法。
3. 运行 Skill 校验、Python 语法检查，以及“空项目、已有项目、重复初始化、不覆盖已有文件”的初始化回归。
4. 检查差异并提交发布变更。
5. 创建带注释的 `vX.Y.Z` tag，并推送 `main` 与 tag。
6. 从该 tag 创建 GitHub Release，至少写明 `Added`、`Changed`、`Fixed` 和 `Migration`；没有内容的栏目可省略。

发布命令示例：

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

不要在仓库还没有通过回归时先打 tag，也不要移动已经公开的 tag。发布后发现兼容性错误，发布新的 `PATCH`；不要悄悄改写旧版本。

### 本地 Skill 如何升级

- 先阅读目标版本的 GitHub Release，特别是 `Migration`。
- 如果本地 Skill 是 Git checkout，切换到目标 tag；需要跟随开发版时才跟随 `main`。
- 如果由 `$skill-installer` 下载，安装器默认不会覆盖已有目录。先保留或移走旧安装副本，再显式安装目标 tag 或最新版本。
- Skill 更新后 Codex 通常会自动发现变化；没有生效时重新打开 Codex。

升级本地 Skill 不会自动修改任何目标项目。

### 已初始化项目如何升级

重新运行新版 `init_project.py` 只会补充缺失内容，不会覆盖已有 `AGENTS.md`、`.agent/` 文档或项目本地脚本。因此：

- `PATCH` 或无迁移要求的 `MINOR`：更新本地 Skill 即可；需要新目录时可重新初始化。
- 需要新增项目文件的兼容版本：重新初始化以创建缺失文件，然后检查输出。
- 需要修改已有模板、脚本或目录的不兼容版本：按照 Release 的迁移说明，在独立分支中显式迁移并重新验证。
- 没有明确迁移说明时，不要让 Agent 批量重写 `.agent/`。

这种策略刻意把项目资料安全放在自动升级便利之前。初始化器不是迁移器；等真实版本演进证明需要重复迁移时，再增加独立、可回滚的迁移脚本。

### 目标项目每次迭代怎么做

同一个工作项继续修改原有 `requirements.md`、`proposal.md` 和 `design.md`，由 Git 保存每次修订。需求发生实质变化时，把最早受影响的文档退回 `draft`，下游标记 `stale`，重新批准并验证。

如果一次产品发布需要可追溯，在 `testing/report.md` 中记录对应的 Git commit 或项目 release tag。不要把 Skill 的 `vX.Y.Z` 和业务项目自己的版本号当成同一个版本体系。

## 边界

- 本 Skill 不替代 Git、源代码、可执行测试、CI 或项目管理平台。
- `.agent/` 保存过程资料和证据，不保存产品实现，也不负责 Skill 发现。
- Git 是历史事实源；`memory.md` 和核心组件 Markdown 都是检索层。
- Agent 不自行批准文档，也不为了迁就现有代码而反向修改已批准需求。
- 初始化和升级默认不覆盖用户已有文件。
