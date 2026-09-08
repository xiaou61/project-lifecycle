# 总索引

这页是仓库的维护地图，回答两个问题：**这类内容应该改哪里？改完到哪里看？**

这里的 `skills/` 是可复用的 Skill 本体，`docs/` 是面向用户的正式教程，根目录 `html/` 是本仓库的理解型可视化产物，`output/` 是生成后的交付文件。初始化到其他项目后，该项目还会拥有自己的 `.agent/INDEX.md` 和 `.agent/html/`。不要把它们混成一个事实源。

## 按模块查找

### 运行时 Skill

| 模块 | 主要位置 | 负责什么 | 改完检查 |
| --- | --- | --- | --- |
| 入口与风险路由 | `skills/project-lifecycle/SKILL.md` | 何时触发 Skill、短路径和不可绕过的底线 | `quick_validate.py` |
| 全流程协议 | `skills/project-lifecycle/references/workflow.md` | 恢复顺序、审批门槛、漂移、依赖和完成语义 | `tests/test_project_status.py` |
| 规则与边界 | `references/rules.md`、`relationships.md`、`specs.md`、`memory.md` | 规则优先级、关系、稳定事实和长期记忆边界 | 状态检查 + 严格校验 |
| 阶段工件规范 | `references/requirements.md`、`proposal.md`、`design.md`、`tasks.md`、`testing.md` | 需求、方案、设计、任务和验证报告怎么写 | 严格校验器 |
| Git 历史视图 | `references/core-history.md` | 核心组件的历史证据和生成约定 | `generate_core_history.py` |
| Codex 界面元数据 | `skills/project-lifecycle/agents/openai.yaml` | UI 显示名称、简述和默认入口 | Skill 校验 |

### 工具与质量

| 模块 | 主要位置 | 负责什么 | 改完检查 |
| --- | --- | --- | --- |
| 初始化器 | `skills/project-lifecycle/scripts/init_project.py` | 幂等创建目标项目的 `.agent/` 和入口模板 | 单元测试 |
| 状态汇总与恢复 | `skills/project-lifecycle/scripts/project_status.py` | 推导阶段、依赖、Git 归因和 `--resume` JSON | 单元测试 + JSON 解析 |
| 严格校验器 | `skills/project-lifecycle/scripts/project_validate.py` | 校验结构、重复 ID、来源、证据和归因 | `--strict` |
| 回归测试 | `tests/test_project_status.py` | 固化生命周期和边界行为 | `python -m unittest discover ...` |

### 面向用户的文档

| 模块 | 主要位置 | 负责什么 | 浏览入口 |
| --- | --- | --- | --- |
| 教程首页 | `docs/index.md` | 用户第一次进入时的概览和入口 | [教程首页](/) |
| 开始使用 | `docs/guide/getting-started.md` | 安装、初始化和第一次工作 | [开始使用](/guide/getting-started) |
| 全流程 | `docs/guide/full-workflow.md` | 需求到完成的阶段说明 | [全流程教程](/guide/full-workflow) |
| 恢复与接力 | `docs/guide/resume.md` | 跨会话恢复、多个工作项和 Git 归因 | [恢复与接力](/guide/resume) |
| 需求与验收 | `docs/guide/requirements.md` | 事实、决定、来源覆盖和验收标准 | [需求、来源与验收](/guide/requirements) |
| 需求深挖访谈 | `docs/guide/requirements-interview.md`、`skills/project-lifecycle/references/requirements-interview.md` | 决策树、逐轮提问、停止条件和 PRD/Task 门槛 | [需求深挖访谈](/guide/requirements-interview) |
| 任务拆分规则 | `skills/project-lifecycle/references/tasks.md` | 纵向切片、真实阻塞关系和 expand-contract 重构 | [全流程教程](/guide/full-workflow) |
| 命令参考 | `docs/reference/commands.md` | 可复制的初始化、状态、恢复和校验命令 | [命令参考](/reference/commands) |
| 边界与常见问题 | `docs/reference/boundaries.md` | 为什么这样设计，以及不负责什么 | [边界与常见问题](/reference/boundaries) |

### 可视化与构建

| 模块 | 主要位置 | 用途 | 约定 |
| --- | --- | --- | --- |
| 本仓库 HTML 理解产物 | `html/` | AI 生成的架构图、流程演示、状态解释和交互草图 | 规则见 `html/README.md`；不作为产品源码 |
| 目标项目导航与 HTML | `.agent/INDEX.md`、`.agent/html/` | 按业务模块定位代码、规格、工作项和项目理解材料 | 由初始化器创建，索引不复制阶段状态 |
| 正式教程源文件 | `docs/` | VitePress 页面和静态资源 | 用 `npm run docs:dev` 预览 |
| 生成交付物 | `output/` | 可下载的 HTML、Draw.io 等最终产物 | 不把这里当运行时事实源 |
| VitePress 配置 | `docs/.vitepress/config.mts` | 导航、侧栏、搜索和站点元信息 | `npm run docs:build` |
| Node 脚本配置 | `package.json` | 教程站开发、构建和预览命令 | `npm run docs:build` |

## 按“我要改什么”定位

| 想改的内容 | 首选文件 | 同步查看或验证 |
| --- | --- | --- |
| 改 Skill 什么时候触发 | `skills/project-lifecycle/SKILL.md` | `references/workflow.md`、Skill 校验 |
| 改某个阶段的规则 | 对应 `references/*.md` | `tests/test_project_status.py`、总索引 |
| 增加状态字段或恢复行为 | `scripts/project_status.py` | 测试、`--json` 输出、命令参考 |
| 增加一个严格质量门槛 | `scripts/project_validate.py` | 测试、`--strict --json` 输出 |
| 改教程文字或新增用户页面 | `docs/guide/` 或 `docs/reference/` | `npm run docs:build`、浏览器页面 |
| 改站点导航或搜索 | `docs/.vitepress/config.mts` | 教程站导航和构建 |
| 做一个帮助理解的独立 HTML | `html/<主题>.html` | 直接打开或用静态服务器预览，并更新 `html/README.md` |
| 生成可交付文件 | `output/` | 对应生成脚本和最终文件检查 |

## 事实源边界

- Skill 的通用规则在 `skills/project-lifecycle/`；目标项目的实际状态在目标项目自己的 `.agent/`。
- 正式教程解释怎么使用，不替代运行时状态，也不手工维护 `WORK-*` 状态。
- `html/` 中的文件用于解释和探索，不能代替源码、测试、需求批准或验证报告。
- 新增模块时，先在对应目录落文件，再在本页补一行入口；索引是导航，不是第二份状态数据库。

## 常用验证

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -X utf8 "C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "skills/project-lifecycle"
npm run docs:build
git diff --check
```
