# Project Lifecycle Skill

一个面向 Codex 的中文项目开发 Skill。它把重要开发工作变成仓库里可检查的资料：当前项目规格、一次变更的提案与设计、实施任务、测试证据，以及会影响后续工作的长期记忆。

[打开交互演示](./demo.html)（克隆或下载仓库后，可直接用浏览器打开，无需安装依赖。）

它借鉴了高星项目中已经验证过的共同做法：Skill 本身保持可复用和渐进披露；项目资料按“当前事实”和“活动变更”组织；流程可以按工作规模收缩，而不是每个小修复都走一套重型仪式。

## Why：它解决什么

Agent 最大的问题通常不是不会写代码，而是会在信息不完整时很快写出“看起来合理”的代码：

- 需求还没确认，就开始选技术方案和改文件。
- 设计、实现和测试各自合理，合在一起却没有对应关系。
- 实现遇到困难后，代码悄悄改变了原来的范围，没人重新确认。
- 下一次会话找不到上次的决策，只能重新猜测。
- 工作做了一半，不知道当前处于哪一步，也不知道下一句话该怎么说。
- 多个需求同时推进时，彼此影响却没有显式关系，改完一个才发现另一个已经失效。
- 项目规则、业务约束和临时功能方案混在同一个目录里，越积越乱。
- Git 有完整历史，但没有按核心组件阅读的视图。

这个 Skill 用尽量少的约定解决这些问题：

```text
当前规格：项目现在应该是什么样
        ^                    |
        | 完成后核对并更新    | 依据
活动变更：这次准备改什么       |
  需求出现 -> 讨论收敛 -> 设计决策 -> 开发实现 -> 测试验收 -> 完成沉淀
                             |
                             +-> 方案 -> 详细设计 -> 实施计划
```

小修复可以只在聊天里给出短设计并直接实现；新项目、跨模块修改、公共接口变化和容易跨会话的工作，才创建完整变更资料。

用户不需要操作这张流程图。直接说“我想加一个功能”“这版需求确认”“方案可以”“继续”“测试一下”或“现在到哪了”即可。Skill 会读取项目工件，判断当前阶段，并用下面的短格式持续给出方向：

```text
当前：用户登录（WORK-003）· 方案选择 · 等待确认
本次：已给出推荐方案和两个真实取舍
下一步：你确认方案后，我会结合当前代码完成详细设计
```

## 整体架构

运行时的心智模型只有两部分：

| 部分 | 职责 |
| --- | --- |
| `project-lifecycle` Skill 包 | 通用规则、阶段参考、初始化器和确定性脚本，任何项目都可以复用 |
| 目标项目的 `.agent/` | 当前项目的规格、活动变更、记忆、决策理由、参考资料和验证证据 |

GitHub、用户级 Skill 目录、仓库级 `.agents/skills/`、插件或本地 checkout，只是同一个 Skill 包的分发或发现方式，不是运行时的额外层。它们不产生项目状态，也不应该和 `.agent/` 混在一起。

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
    rules/
      always.md                     当前项目所有任务都适用的常驻规范
    memory.md                       可检索的跨任务长期记忆
    specs/                          当前仍有效的共享规格、契约和边界
      auth.md
      architecture.md
    changes/                         活动变更
      WORK-003-用户登录/
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
| `.agent/changes/WORK-编号-中文名/` | “这次要改什么，为什么改，怎样证明改对？” | 从 draft 到完成，可归档但不删除 |

`specs/` 不是需求草稿的回收站，`changes/` 也不是永久系统百科。完成变更后，如果公共行为真的改变，才把验证后的结果合并回 `specs/`。

其他目录保持单一职责：

- `rules/always.md`：这个项目每个任务都必须重新加载的长期规范；技术栈、目录、命令和安全边界放这里。
- `memory.md`：下一次 Agent 需要快速想起什么。
- `notes/`：为什么做出某个跨变更决策。
- `references/`：项目依赖的共享事实、协议、业务规则或外部资料。
- `history/`：从 Git 重建的可读历史，不是手工事实源。

## Skill 包里每个文件解决什么痛点

| 文件 | 解决的问题 |
| --- | --- |
| `SKILL.md` | 防止 Agent 跳过必要阶段、自行批准或无声扩大范围；只放共享规则和阶段路由。 |
| `agents/openai.yaml` | 让 Codex UI 能识别 Skill，并提供中文默认调用入口。 |
| `references/rules.md` | 定义全局底线、项目常驻规范、工作项约束的边界、优先级和上下文压缩恢复顺序。 |
| `references/workflow.md` | 唯一的自然语言执行与跨对话接力协议；规定触发、恢复顺序、阶段门槛、`WORK-*` 接力和标准状态输出。 |
| `references/relationships.md` | 固定中文工作项名称和编号，区分硬依赖、软关联以及应该合并的需求。 |
| `references/requirements.md` | 把模糊想法变成目标、非目标、约束和可观察验收标准。 |
| `references/proposal.md` | 分开“要什么”和“选什么方案”，保留真实取舍。 |
| `references/design.md` | 固定当前仓库中的组件边界、接口、数据流和失败行为。 |
| `references/tasks.md` | 把批准的设计拆成有依赖关系、可执行、可验证的任务，避免设计批准后直接凭感觉编码。 |
| `references/testing.md` | 把验收标准映射到实际命令、人工检查和未验证项。 |
| `references/specs.md` | 说明什么资料才算项目的稳定当前事实，以及完成变更后如何回写。 |
| `references/memory.md` | 约束长期记忆的格式、证据、失效和检索方式，避免记忆变成聊天日志。 |
| `references/core-history.md` | 规定 Git 是事实源，Markdown 只是按核心组件生成的阅读视图。 |
| `scripts/init_project.py` | 幂等初始化目标项目，缺什么补什么，不覆盖已有资料。 |
| `scripts/project_status.py` | 只读汇总中文名称、阶段、任务计数、依赖、关联、阻塞和下一步，不另建状态数据库。 |
| `scripts/generate_core_history.py` | 确定性读取 Git，生成提交时间、作者、哈希和变更路径。 |
| `tests/test_project_status.py` | 验证阶段推导和已有项目初始化不会覆盖用户文件。 |

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
- 创建 `.agent/specs/`、`.agent/changes/`、`.agent/rules/`、`notes/`、`references/`、`history/`、`scripts/`、`rules/always.md` 和 `memory.md`；
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
.agent/project/              -> .agent/changes/WORK-编号-项目基础/
.agent/features/<name>/      -> .agent/changes/WORK-编号-中文名/
```

先扫描活动和归档工作项确定下一个可用编号，再迁移。迁移必须由用户在独立分支中检查后完成，因为旧资料可能有自定义目录、链接或未完成状态。
迁移完成后，还要同步修改旧 `AGENTS.md` 和 `.agent/README.md` 中对 `project/`、`features/` 的引用；初始化器会保留这两个文件，不会替你覆盖。

## 操作手册：只用自然语言

### 1. 开始一个需求

你可以直接说：

```text
我想增加用户登录，先聊聊这个需求。
```

如果这是重要开发且项目还没有 `.agent/`，Skill 会先初始化项目资料目录；已有源码、测试、Git 和项目文档不会被覆盖。然后 Agent 会读取相关代码、规格和长期记忆，只追问会改变范围、行为、约束或验收的问题。

Agent 会在第一次回应中主动给需求一个简短中文名称，并在持久化时分配稳定编号，例如：

```text
当前：用户登录（WORK-003）· 需求讨论 · 草稿
```

目录使用 `.agent/changes/WORK-003-用户登录/`。中文名称贯穿需求、提案、设计、任务和测试；`WORK-003` 永不复用，专门解决重名、改名和跨需求引用问题。

### 2. 按阶段自然推进

| 当前阶段 | Agent 负责 | 你需要做的决定 | 留下的结果 |
| --- | --- | --- | --- |
| 需求讨论 | 理清背景、目标、非目标、约束和可观察验收标准 | “这版需求确认”或指出需要修改的地方 | `requirements.md` |
| 方案选择 | 推荐一个方案，说明真实备选、取舍和仓库影响 | “方案可以”或选择其他方案 | `proposal.md` |
| 详细设计 | 结合真实代码确定组件、接口、数据流、失败处理和测试策略 | “设计没问题”或指出设计调整 | `design.md` |
| 实施计划 | 把设计拆成依赖有序、路径真实、每项可验证的任务 | “按这个计划做”或调整任务顺序 | `tasks.md` |
| 开发实现 | 按批准计划改代码、写可执行测试、同步任务状态 | 只处理实质偏离或外部阻塞 | 源码、测试和实际任务状态 |
| 测试验收 | 按验收标准运行检查，记录通过、失败和未验证项 | 决定是否接受剩余风险 | `testing/plan.md`、`testing/report.md` |
| 完成沉淀 | 核对稳定规格，只沉淀真正跨任务的长期知识 | 决定是否归档 | `specs/`、`memory.md` 和可选归档 |

从你的视角，标准主线就是“需求出现 → 讨论 → 设计 → 开发 → 测试 → 沉淀”。表中的方案、详细设计和实施计划只是设计阶段内部逐步变具体的检查点，不需要你学习另一套操作方式。

你不必说 `requirements.md`、`proposal.md` 这些文件名。下面这些普通表达已经足够：

```text
这版需求确认，继续给方案。
方案可以，结合现在的代码做设计。
设计没问题，拆成任务。
按这个计划开始做。
测试一下，告诉我哪些验收项过了。
当前任务状态是什么？
所有需求有哪些阻塞？
继续。
```

其中“继续”只表示继续当前阶段已经获准的工作，不代表批准。如果当前工件正在等待确认，Agent 会明确告诉你正在等哪一个决定，而不会擅自跨阶段。

### 3. 查询当前状态

直接说下面任何一句即可：

```text
当前任务状态。
用户登录现在到哪一步了？
查询 WORK-003。
所有需求的状态和阻塞关系。
TASK-002 做完了吗？
```

默认结果包括中文名称、`WORK-*` 编号、当前阶段、状态、内部任务计数、硬依赖、软关联、阻塞原因和下一步。点名 `TASK-*` 时，Agent 会进一步读取当前工作项的 `tasks.md`。

手工执行只读查询：

```powershell
# 当前非归档工作项
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目"

# 按中文名称或稳定编号查询
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work "用户登录"
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work WORK-003

# 包含历史归档
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --include-archive
```

### 4. 用 `WORK-*` 跨对话接力

换一个会话后不需要重新解释需求。推荐直接说：

```text
$project-lifecycle 在当前项目继续实施 WORK-003。先恢复规范和状态；满足实施门槛就按已批准任务计划改代码并测试，否则告诉我还缺什么确认。
```

如果新对话已经打开目标项目，并且根 `AGENTS.md` 已正确路由本 Skill，可以简写为：

```text
继续实施 WORK-003。
```

`WORK-003` 只是定位该需求全部持久资料的键，不是直接写代码的命令，也不代表批准。Skill 会从项目规范、工件身份、关系、`status`、内部任务状态和测试报告重新推导现场：任务计划已批准且没有阻塞就直接实施；否则停在最早缺失阶段，告诉你需要确认什么。它不会依赖聊天记忆，也不会维护一份容易和真实资料冲突的 `.agent/current.md` 或 `state.json`。

这个行为完整写在 [`references/workflow.md`](./references/workflow.md)，它是唯一的执行与接力协议。每次已有编号的工作项实质推进后，Agent 必须给出：

```text
当前：用户登录（WORK-003）· 开发实现 · 进行中
本次：完成 TASK-002，并运行相关单元测试
下一步：继续 TASK-003
接力：新对话可说“$project-lifecycle 继续 WORK-003，先恢复规范和状态，再按当前阶段执行。”
```

因此你不需要记住全部规范，只需要保留真实的 `WORK-*`；新会话会从仓库文件重新加载规则和批准状态。如果存在多个活动工作项且描述不能唯一匹配，Agent 才会问你要继续哪一个。

### 5. 需求之间互相影响

只保留两种关系：

| 关系 | 什么时候用 | 会发生什么 |
| --- | --- | --- |
| `depends_on` 硬依赖 | B 必须等 A 交付后才能正确实现或验收 | B 可以先讨论和设计，但进入开发前会被阻塞 |
| `related_to` 软关联 | A、B 共享接口、数据、模块或决策，但可以独立交付 | 不阻塞；跨阶段前检查对方是否需要退回 `draft` 或标记 `stale` |

如果两个需求不能独立批准和验收，它们本质上就是同一个工作项，应在需求阶段合并。如果形成 `A -> B -> A` 循环依赖，则合并它们，或者抽出一个双方共同依赖的前置工作项。仅仅修改同一个文件，不足以建立需求关系。

关系保存在各自 `requirements.md` 中：

```yaml
work_id: WORK-003
work: 用户登录
depends_on: [WORK-001]
related_to: [WORK-002]
```

状态查询器会自动给出反向视图，因此 `WORK-001` 也能看到“被 WORK-003 依赖”，不需要维护中央依赖表。

### 6. 小改动自动走短路径

单文件、低风险、行为边界清楚的小修复，可以只在聊天里确认目标和最小思路，随后实现并验证，不创建完整变更目录。新项目、重要功能、跨模块修改、公共接口变化、迁移、安全或架构调整默认走完整流程。

### 7. 发生变化时回到正确阶段

目标、验收标准、公共行为、接口、数据、安全、迁移或架构发生实质变化时，Agent 会停止当前阶段，修改最早受影响的工件，并将下游工件标记为 `stale`。局部变量改名或批准设计范围内的实施细节不会触发整套重审。

完成后，如果公共规则发生变化，会根据验证结果更新 `.agent/specs/`；只有真正影响未来任务的知识才进入 `memory.md`。同一工作项使用稳定文件名，Git 保存修订历史，不创建 `design-v2-final.md` 或 `final-final.md`。

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

## 规范分级与上下文恢复

开发时不要把所有规则都塞进同一个提示词。Skill 维护一组所有项目通用的全局底线；初始化后的项目维护 `.agent/rules/always.md`，记录这个仓库每个任务都必须遵守的技术、目录、命令、安全和兼容性规范；本次需求的特殊限制则写入对应 `requirements.md`。三者分别回答：

| 层级 | 适用范围 | 典型内容 | 保存位置 |
| --- | --- | --- | --- |
| 全局底线 | 所有项目、所有受管理任务 | 中文沟通、先查状态、明确批准、不覆盖资料、不虚报测试、控制漂移 | Skill 的 `SKILL.md` |
| 项目常驻规范 | 当前项目的每一个任务 | 技术栈、源码/测试目录、必须命令、生成文件、安全和兼容性 | `.agent/rules/always.md` |
| 工作项约束 | 当前 `WORK-*` | 本次目标、非目标、验收标准、特殊边界和已批准例外 | `.agent/changes/.../requirements.md` |

使用 `MUST / SHOULD / MAY` 写项目规则：硬约束、默认做法、可选建议。初始化模板的 frontmatter 使用 `configured: false`；补全项目事实后改为 `configured: true`。工作项可以更严格，不能静默取消项目常驻规范；需要例外时记录理由、批准人、有效范围和验证方式。状态查询同时返回 `rules.ready` 和 `rules.configured`：前者表示规则文件结构可加载，后者表示项目事实已经补全。缺失或冲突时不能实现；尚未配置完整时可以讨论和设计，但进入实现前必须补全本次工作依赖的项目事实。

上下文压缩后不依赖聊天记忆。每次恢复按固定顺序读取 `AGENTS.override.md`、`AGENTS.md`、`.agent/rules/always.md`、状态查询 JSON、当前工作项 `requirements.md` 和本阶段批准工件，并重新输出“当前 / 本次 / 下一步”。因此即使上一轮的规则没有留在上下文里，项目文件仍是可恢复的事实源。

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
