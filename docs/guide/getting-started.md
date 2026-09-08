# 开始使用

这套 Skill 管理的是需要跨会话追踪、多人协作或有明显风险的开发工作。单文件、低风险、边界清楚的小修复不需要为了形式创建工作项。

## 1. 安装 Skill

在 Codex 中运行：

```text
使用 $skill-installer 从 https://github.com/xiaou61/project-lifecycle/tree/main/skills/project-lifecycle 安装 project-lifecycle。
```

也可以把仓库 checkout 到 Codex 支持的 Skill 发现目录。安装后无需把某台机器的绝对路径写进项目规则。

## 2. 初始化项目资料

初始化只增加 `.agent/` 资料目录和入口模板，不移动源码、不创建空白工作项，也不会替你猜测项目规则：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\init_project.py" "F:\我的项目"
```

初始化后的关键目录如下：

```text
我的项目/
├─ AGENTS.md
├─ .agent/
│  ├─ rules/always.md
│  ├─ INDEX.md
│  ├─ memory.md
│  ├─ specs/
│  ├─ changes/
│  └─ html/
└─ 你的源码和测试/
```

`INDEX.md` 是按模块整理的导航页，告诉你源码、测试、规格和相关变更到哪里看；它不复制工作项状态。`html/` 用于保存 AI 生成的架构图、流程演示、状态机或其他项目理解材料。

## 3. 确认项目常驻规则

首次初始化后，Agent 会先检查仓库并提出规则草案。你确认后再创建 `.agent/rules/always.md`。

规则未确认时仍可做需求讨论、设计和不依赖未知规则的只读验证；实现、部署、迁移和数据变更会被阻断。这是为了避免 Agent 把一次聊天里的临时偏好误当成长期项目规则。

## 4. 从自然语言开始

不需要记固定口令，直接描述目标即可：

```text
我想增加用户登录，先聊聊这个需求。
```

当需求稳定后：

```text
这版需求确认，继续给方案。
方案可以，结合当前代码做设计。
设计没问题，按它拆任务。
任务计划确认，开始做。
```

每个需要持久追踪的需求都会得到一个稳定的中文名称和 `WORK-*` 编号。编号用于定位，不代表任何阶段已经批准。

## 5. 查看状态

查询当前活动工作项：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目"
```

查询指定工作项：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work WORK-003
```

准备换对话或恢复工作时，使用恢复输出：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --resume
```

需要让 Agent 读取结构化结果时加 `--json`。完整流程见[跨会话恢复与接力](/guide/resume)。

## 6. 什么时候不用它

以下情况可以直接确认目标、修改并做窄验证：

- 一个文件的小改动，边界和验收都明确；
- 不涉及公共接口、数据迁移、安全、部署或架构；
- 不需要下一次对话继续追踪。

不要为了填写工件而把这种改动包装成完整项目。
