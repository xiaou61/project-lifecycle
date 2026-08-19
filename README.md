# Project Lifecycle Skill

一个面向 Codex 的中文项目开发生命周期 Skill。它通过需求、提案、设计、实现和验证五个阶段控制项目漂移，并把项目过程资料统一保存在目标项目的 `.agent/` 目录。

## 先理解三个位置

这个项目涉及三个不同位置。Skill 本体确实需要安装到 Codex 能发现的本地目录；仅仅把源码仓库放在任意文件夹里，并不会完成安装。`.agent/` 只是 Skill 在某个目标项目中创建的项目资料目录。

### 1. GitHub 源码仓库

这是用于版本管理和开源分发的源代码：

```text
https://github.com/xiaou61/project-lifecycle

project-lifecycle/
  SKILL.md                 Skill 指令入口
  agents/openai.yaml       UI 元数据
  references/              按需读取的详细规范
  scripts/                 初始化器和确定性辅助脚本
```

### 2. Codex 本地安装目录

Codex 实际从这里加载 `$project-lifecycle`。安装后的内容与 GitHub 仓库保持同样的 Skill 结构：

```text
Windows（本机 bundled skill-installer 的默认位置）
C:\Users\<用户名>\.codex\skills\project-lifecycle\
  SKILL.md
  agents/
  references/
  scripts/
```

某些 Codex 配置也使用 `~/.agents/skills/` 作为用户级发现目录；关键是使用当前环境声明的 Skill 安装/发现目录，不要把 Skill 放进目标项目的 `.agent/`。

### 3. 被管理的目标项目

这是你的业务项目。Skill 安装后，在这里运行初始化器：

```text
your-project/
  AGENTS.md                Codex 项目级入口规则（初始化时缺失才创建）
  .agent/                  本项目的生命周期资料和长期记忆
  src/                     项目源代码
  tests/                   项目可执行测试
```

这样分开是有意的：同一个 Skill 可以管理多个项目并独立升级；每个项目的需求、决策、记忆和验证结果则跟随各自项目保存。如果把 Skill 本体复制进每个 `.agent/`，会造成重复版本、升级困难，并把通用指令和项目状态混在一起。

## 安装到本地

在 Codex 中可以直接调用安装器：

```text
使用 $skill-installer 从 https://github.com/xiaou61/project-lifecycle 安装 project-lifecycle。
```

在 Windows PowerShell 中也可以执行 bundled installer：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo xiaou61/project-lifecycle `
  --path . `
  --name project-lifecycle
```

安装完成后，Codex 会从本地安装目录加载 `$project-lifecycle`。如果当前会话没有显示新 Skill，重启 Codex。`AGENTS.md` 不能替代安装，它只负责告诉 Codex 在目标项目中何时使用已安装的 Skill。

## 初始化目标项目

先安装 Skill，再在目标项目根目录调用：

```text
使用 $project-lifecycle 初始化当前项目，创建 .agent 工作区。
```

或者直接运行本地安装副本中的初始化器：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\init_project.py" "F:\我的已有项目"
```

初始化器会在目标项目根目录缺少 `AGENTS.md` 时创建一份最小入口规则，并创建或补充 `.agent/`；不会复制整个 Skill，也不会修改源代码、测试、依赖配置或 Git 历史。已有 `AGENTS.md`、`AGENTS.override.md` 和 `.agent/` 文件都会保留。初始化器不会自动向已有 `AGENTS.md` 合并内容，而是提示你确认其中是否已经包含生命周期规则。

生成结构：

```text
your-project/
  AGENTS.md                缺失时创建；已有文件不覆盖
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

根目录的 `AGENTS.md` 只负责路由：重要功能使用 `$project-lifecycle`，具体资料仍写入 `.agent/`。如果存在 `AGENTS.override.md`，Codex 会优先使用它。

初始化可以重复执行。已有文件会被保留，不会被覆盖。

## 项目长期记忆

`.agent/memory.md` 保存当前仍有效、会影响后续多个任务的项目知识。它不是聊天记录、开发日志或待办清单。

一条记忆使用固定格式：

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

支持的状态为 `active | stale | superseded`，常用类别为 `constraint | architecture | convention | preference | operation | lesson`。ID 创建后不重新编号，也不复用。

快速列出全部记忆：

```sh
rg -n "^## MEM-" .agent/memory.md
```

按模块、标签或关键词搜索：

```sh
rg -n -i -C 6 "auth|session|security" .agent/memory.md
```

开始重要任务时先检索相关记忆；结束时只沉淀可能影响未来任务的知识。任务进度、临时错误、聊天摘要、未经证实的猜测和密钥不得写入长期记忆。

三个位置的职责不同：

- `memory.md`：现在需要记住什么，要求短小、有效、方便检索。
- `notes/`：为什么做出某个跨功能决策，保存完整理由和取舍。
- `references/`：项目共享的外部事实、业务规则、协议或资料。

## 日常开发流程

### 1. 讨论需求

```text
使用 $project-lifecycle 开始“用户登录”功能。
先检查项目并和我讨论需求，不要设计，也不要写代码。
```

确认讨论结果后：

```text
把结果写入 .agent/features/user-login/requirements.md，保持 draft。
```

### 2. 批准需求并生成提案

```text
我批准当前需求，请标记为 approved，并生成 proposal.md。不要编码。
```

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

项目资料最终形态：

```text
.agent/features/user-login/
  requirements.md
  proposal.md
  design.md
  testing/
    plan.md
    report.md
```

### 6. 对齐审计

```text
使用 $project-lifecycle 执行最终对齐审计，检查需求、提案、设计、代码、测试和验证报告是否一致。
```

## 防止项目漂移

上游发生实质变化时，必须回到最早受影响的文档：

```text
修改上游文档并回到 draft
  -> 受影响的下游文档标记 stale
  -> 用户重新批准
  -> 依次更新下游文档
  -> 重新实现和验证
```

Agent 不能自行批准文档，也不能修改需求来迁就已经写出的代码。

## 核心组件历史

在 `.agent/core-components.json` 中声明核心组件：

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

Git 是提交时间、作者、哈希和文件变化的唯一事实源；生成的 Markdown 只是可重建视图。
