# Project Lifecycle Skill

一个面向 Codex 的中文项目开发生命周期 skill。它通过需求、提案、设计、实现和验证五个阶段控制项目漂移，并把项目过程资料统一保存在目标项目的 `.agent/` 目录。

## 两个目录不要混淆

```text
project-lifecycle/          本开源 skill 仓库
  SKILL.md
  agents/
  references/
  scripts/

your-project/               被管理的目标项目
  .agent/                   skill 初始化的项目资料目录
  src/                      项目源代码
  tests/                    项目可执行测试
```

`.agents/skills` 是 Codex 查找已安装 skill 的标准位置；`.agent/` 是本 skill 为目标项目定义的工作区。两者用途不同。

## 安装

把本仓库目录安装或链接到用户级 skill 目录：

```text
~/.agents/skills/project-lifecycle/
```

也可以发布到 GitHub 后，让 Codex 使用 `$skill-installer` 从仓库地址安装。Codex 没有立即显示新 skill 时，重新启动 Codex。

## 初始化项目

在目标项目中调用：

```text
使用 $project-lifecycle 初始化当前项目，创建 .agent 工作区。
```

初始化器实际执行：

```sh
python <skill目录>/scripts/init_project.py <目标项目目录>
```

生成结构：

```text
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
