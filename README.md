# Project Lifecycle Skill

一个面向 Codex 的中文项目开发 Skill。它把重要开发工作变成仓库里可检查的资料：当前项目规格、一次变更的提案与设计、实施任务、测试证据，以及会影响后续工作的长期记忆。

它借鉴了高星项目中已经验证过的共同做法：Skill 本身保持可复用和渐进披露；项目资料按“当前事实”和“活动变更”组织；流程可以按工作规模收缩，而不是每个小修复都走一套重型仪式。

## Why：它解决什么

Agent 最大的问题通常不是不会写代码，而是会在信息不完整时很快写出“看起来合理”的代码：

- 需求还没确认，就开始选技术方案和改文件。
- 设计、实现和测试各自合理，合在一起却没有对应关系。
- 实现遇到困难后，代码悄悄改变了原来的范围，没人重新确认。
- 下一次会话找不到上次的决策，只能重新猜测。
- 项目规则、业务约束和临时功能方案混在同一个目录里，越积越乱。
- Git 有完整历史，但没有按核心组件阅读的视图。

这个 Skill 用尽量少的约定解决这些问题：

```text
当前规格：项目现在应该是什么样
        ^                    |
        | 完成后核对并更新    | 依据
活动变更：这次准备改什么       |
  需求 -> 提案 -> 设计 -> 任务 -> 实现 -> 验证
```

小修复可以只在聊天里给出短设计并直接实现；新项目、跨模块修改、公共接口变化和容易跨会话的工作，才创建完整变更资料。

## 先说结论：之前的三层说法不准确

此前把下面三件事称为“整体架构的三层”：

1. GitHub 源码仓库；
2. Codex 本地安装目录；
3. 目标项目。

这其实是**分发链路**，不是运行时架构。高星 Skill 项目通常也不会把安装位置画成工作流的一层。

正确的心智模型只有两部分：

| 部分 | 职责 |
| --- | --- |
| `project-lifecycle` Skill 包 | 通用规则、阶段参考、初始化器和确定性脚本，任何项目都可以复用 |
| 目标项目的 `.agent/` | 当前项目的规格、活动变更、记忆、决策理由、参考资料和验证证据 |

GitHub、用户级 Skill 目录、仓库级 `.agents/skills/`、插件或本地 checkout，只是把同一个 Skill 包分发/发现出来的不同方式。它们不产生额外的项目状态，也不应该和 `.agent/` 混在一起。

官方 Codex 文档规定 Skill 是包含 `SKILL.md` 的目录，可选 `references/`、`scripts/`、`assets/` 和 `agents/openai.yaml`；Codex 会从仓库、用户、管理员和系统范围发现它。参见 [Build skills](https://learn.chatgpt.com/docs/build-skills)。

## 参考了哪些高星项目

这里不是照搬某个项目，而是抽取它们共同有效的部分（星数会变化，链接是事实来源）：

| 项目 | 观察到的结构 | 我们采用的启发 |
| --- | --- | --- |
| [Anthropic Skills](https://github.com/anthropics/skills) | 每个 Skill 自包含一个 `SKILL.md`，详细资料和脚本按需放在 Skill 内 | Skill 包保持独立；`references/` 不变成项目状态目录 |
| [Superpowers](https://github.com/obra/superpowers) | 按能力拆分可组合 Skill；头脑风暴、计划、执行、验证分别承担清晰职责 | 需要实施任务阶段；流程应该按工作规模收缩 |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | 项目初始化后生成项目内规格和工作资料，并区分短路径与完整路径 | 工具安装和项目工件分开；不是所有工作都需要完整路径 |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | `specs/` 表示当前事实，`changes/<name>/` 表示一次活动变更，完成后归档 | 本项目采用的核心目录模型 |

因此，本项目不再使用 `.agent/project/` 和 `.agent/features/` 两套并行入口，也不把安装目录称为架构层。

### 为什么仍然是一个 Skill

Superpowers 适合把头脑风暴、TDD、调试、代码审查等可独立复用的能力拆成多个 Skill。本项目的需求、提案、设计、任务和验证则共享同一组状态、审批关系和变更目录，拆成多个 Skill 会增加安装、发现和跨 Skill 交接成本。

因此当前保持一个编排 Skill：`SKILL.md` 只放共同规则，进入某个阶段时才读取对应 `references/*.md`。将来只有某个能力能够独立安装、独立触发、独立完成时，才把它拆成单独 Skill。

## 目标项目的实际结构

初始化后，目标项目只增加一个项目资料工作区：

```text
your-project/
  AGENTS.md                         项目级路由，可选地由初始化器创建
  AGENTS.override.md                用户自己的更高优先级规则（如有）
  .agent/
    README.md                       工作区说明
    memory.md                       可检索的跨任务长期记忆
    specs/                          当前仍有效的共享规格、契约和边界
      auth.md
      architecture.md
    changes/                         活动变更
      add-login/
        requirements.md
        proposal.md
        design.md
        tasks.md
        testing/
          plan.md
          report.md
      archive/                       已完成变更的可选归档
    notes/                           跨变更决策理由
    references/                      共享业务规则、协议和外部资料
    history/                         Git 生成的核心组件历史视图
    scripts/                         项目本地确定性辅助脚本
  src/                              产品源代码（项目原有位置）
  tests/                            可执行测试（项目原有位置）
```

### 两个核心目录的区别

| 目录 | 回答的问题 | 生命周期 |
| --- | --- | --- |
| `.agent/specs/` | “项目现在应该怎样工作？” | 稳定、跨变更复用；只有已验证的当前事实才进入 |
| `.agent/changes/<工作项>/` | “这次要改什么，为什么改，怎样证明改对？” | 从 draft 到完成，可归档但不删除 |

`specs/` 不是需求草稿的回收站，`changes/` 也不是永久系统百科。完成变更后，如果公共行为真的改变，才把验证后的结果合并回 `specs/`。

其他目录保持单一职责：

- `memory.md`：下一次 Agent 需要快速想起什么。
- `notes/`：为什么做出某个跨变更决策。
- `references/`：项目依赖的共享事实、协议、业务规则或外部资料。
- `history/`：从 Git 重建的可读历史，不是手工事实源。

## Skill 包里每个文件解决什么痛点

| 文件 | 解决的问题 |
| --- | --- |
| `SKILL.md` | 防止 Agent 跳过必要阶段、自行批准或无声扩大范围；只放共享规则和阶段路由。 |
| `agents/openai.yaml` | 让 Codex UI 能识别 Skill，并提供中文默认调用入口。 |
| `references/requirements.md` | 把模糊想法变成目标、非目标、约束和可观察验收标准。 |
| `references/proposal.md` | 分开“要什么”和“选什么方案”，保留真实取舍。 |
| `references/design.md` | 固定当前仓库中的组件边界、接口、数据流和失败行为。 |
| `references/tasks.md` | 把批准的设计拆成有依赖关系、可执行、可验证的任务，避免设计批准后直接凭感觉编码。 |
| `references/testing.md` | 把验收标准映射到实际命令、人工检查和未验证项。 |
| `references/specs.md` | 说明什么资料才算项目的稳定当前事实，以及完成变更后如何回写。 |
| `references/memory.md` | 约束长期记忆的格式、证据、失效和检索方式，避免记忆变成聊天日志。 |
| `references/core-history.md` | 规定 Git 是事实源，Markdown 只是按核心组件生成的阅读视图。 |
| `scripts/init_project.py` | 幂等初始化目标项目，缺什么补什么，不覆盖已有资料。 |
| `scripts/generate_core_history.py` | 确定性读取 Git，生成提交时间、作者、哈希和变更路径。 |

## 初始化器会做什么

在目标项目根目录运行：

```text
使用 $project-lifecycle 初始化当前项目。
```

或直接运行：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\init_project.py" "F:\我的项目"
```

它会：

- 缺少时创建根 `AGENTS.md`；
- 创建 `.agent/specs/`、`.agent/changes/`、`notes/`、`references/`、`history/`、`scripts/` 和 `memory.md`；
- 把核心历史脚本复制到目标项目；
- 允许对空项目、已有项目和重复执行；
- 保留已有 `AGENTS.md`、`AGENTS.override.md`、`.agent/` 文件、源代码和 Git 历史。

它不会：

- 安装 Skill 本身；
- 把 Skill 包复制到 `.agent/`；
- 修改源代码、测试、依赖、分支或提交；
- 自动把旧目录移动到新目录；
- 自动创建完整的空白需求、设计或测试文档。

如果检测到旧版 `.agent/project/` 或 `.agent/features/`，初始化器只提示迁移建议并原样保留：

```text
.agent/project/              -> .agent/changes/project-foundation/
.agent/features/<name>/      -> .agent/changes/<name>/
```

迁移必须由用户在独立分支中检查后完成，因为旧资料可能有自定义目录、链接或未完成状态。
迁移完成后，还要同步修改旧 `AGENTS.md` 和 `.agent/README.md` 中对 `project/`、`features/` 的引用；初始化器会保留这两个文件，不会替你覆盖。

## 日常工作流

### 小改动

对于单文件、低风险、已有行为内的修改，可以在聊天中完成短设计、获得确认、实现并验证，不创建完整变更目录。

### 重要变更

所有资料放在同一个 `.agent/changes/<work-slug>/` 下：

```text
requirements -> proposal -> design -> tasks -> implementation -> testing
```

示例调用：

```text
使用 $project-lifecycle 开始“用户登录”功能。
先读取相关 specs 和 memory，和我讨论需求，不要写代码。
```

```text
把确认后的内容写入 .agent/changes/user-login/requirements.md，保持 draft。
```

```text
我明确批准 requirements.md。请生成 proposal.md，不要编码。
```

```text
我批准 proposal.md。请结合当前代码生成 design.md，不要实现。
```

```text
我批准 design.md。请生成 tasks.md，列出真实文件、依赖和验证命令，不要实现。
```

```text
我批准 tasks.md。请按任务顺序实现并更新任务状态；如果需要实质性偏离，先停止。
```

```text
进入验证阶段，生成 testing/plan.md，运行相关检查，并依据实际结果生成 testing/report.md。
```

完成后，如果公共规则发生变化：

1. 根据验证结果更新 `.agent/specs/`；
2. 保留完整的 `changes/<work-slug>/`；
3. 可选地移动到 `.agent/changes/archive/YYYY-MM-DD-<work-slug>/`。

不要创建 `design-v2-final.md` 或 `final-final.md`。同一工作项使用稳定文件名，Git 保存修订历史，frontmatter 保存当前状态。

## 防止项目漂移

实质变化包括目标、非目标、验收标准、公共行为、接口、数据、安全、迁移或架构。发生变化时：

```text
找到最早受影响的文档
  -> 退回 draft
  -> 下游文档标记 stale
  -> 用户重新批准
  -> 重新生成后续文档和 tasks
  -> 重新实现与验证
  -> 最后更新 specs/
```

局部变量改名、等价库调用或任务内新增的验证步骤通常不是实质变化。Agent 不能为了让代码看起来合规而事后改写批准过的需求或稳定规格。

## 长期记忆与核心历史

`memory.md` 只保存跨任务仍有价值、且有证据的知识。快速检索：

```sh
rg -n "^## MEM-" .agent/memory.md
rg -n -i -C 6 "auth|session|security" .agent/memory.md
```

核心组件历史由 Git 生成：

```sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

Git 是提交时间、作者、哈希和路径的唯一事实源；Markdown 可以重建，不应手工追加，也不应由 hook 自动创建第二个提交。

## 安装与分发

这部分是安装说明，不是项目架构。

在 Codex 中推荐：

```text
使用 $skill-installer 从 https://github.com/xiaou61/project-lifecycle 安装 project-lifecycle。
```

也可以把本仓库 checkout 到 Codex 支持的 Skill 发现目录，或通过插件分发。不同环境的发现目录可能不同；以当前 Codex 文档和 `$skill-installer` 输出为准，不要把某台机器的绝对路径写进项目规则。

## 版本与升级

Skill 包使用 Git tag 管理版本：

- `PATCH`：文档或兼容性修复；
- `MINOR`：向后兼容的新参考、新阶段或初始化能力；
- `MAJOR`：不兼容的 `.agent/` 结构、状态语义或初始化行为变化。

在 `v1.0.0` 之前使用 `v0.MINOR.PATCH`；`0.x` 的结构调整仍必须在 Release 中明确迁移影响。Git tag 是正式版本的事实源，未打 tag 的 `main` 只是开发版本。

每个 Skill 版本按下面的最小流程发布：

1. 根据兼容性选择 `PATCH`、`MINOR` 或 `MAJOR`，不按修改文件数量决定。
2. 更新 README；不兼容变化必须写清受影响目录、迁移步骤和回滚方式。
3. 运行 Skill 校验、Python 语法检查，以及新项目、已有项目、重复初始化、路径冲突和不覆盖已有文件的回归。
4. 检查差异并提交发布变更。
5. 创建带注释的 `vX.Y.Z` tag，推送代码和 tag。
6. 创建 GitHub Release，按实际内容写 `Added`、`Changed`、`Fixed` 和 `Migration`。

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

公开 tag 不移动、不覆盖。发布后发现问题，创建新的 `PATCH` 版本。

目标项目的变更版本不使用 Skill 的版本号：使用稳定文件名、frontmatter、Git 历史和可选归档目录。

升级顺序：

1. 阅读目标 Skill 版本的 Release 说明和迁移部分；
2. 更新本地 Skill 包；
3. 对目标项目重新运行初始化器，只补充缺失目录；
4. 如果存在不兼容结构变化，在独立分支手工迁移并运行对齐审计；
5. 没有迁移说明时，不让 Agent 批量重写已有 `.agent/`。

初始化器不是迁移器。只有当真实版本演进证明手工迁移重复且规则稳定时，才值得增加独立迁移脚本。

## 边界

- 不替代 Git、CI、测试框架或项目管理平台。
- 不把聊天记录、临时错误或秘密写入长期记忆。
- 不凭提交信息猜测“核心类”；核心组件必须由项目显式配置路径。
- 不强迫低风险小改动创建完整文档。
- 不自动批准、不自动扩大范围、不覆盖用户已有资料。
