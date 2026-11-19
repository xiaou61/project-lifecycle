# 命令参考

这些是给用户和自动化调用的稳定入口。底层 Python 文件属于 Skill 实现细节，普通用户不需要直接运行 Python。

```powershell
$lifecycle = "<已安装 Skill 目录>/project-lifecycle/scripts/project-lifecycle.ps1"   # macOS/Linux 用 project-lifecycle.sh
```

## 初始化

```powershell
& $lifecycle init "F:\我的项目"
```

初始化器是幂等的：已有 `AGENTS.md`、`.agent/`、源码、测试和 Git 历史会被保留。

## 状态查询

```powershell
# 当前活动工作项（精简，默认用这个）
& $lifecycle brief "F:\我的项目"
& $lifecycle brief "F:\我的项目" --json

# 完整清单（含签署、预算与全部提示）
& $lifecycle status "F:\我的项目"

# 按编号或中文名称查询
& $lifecycle status "F:\我的项目" --work WORK-003
& $lifecycle status "F:\我的项目" --work "用户登录"

# 恢复上下文
& $lifecycle resume "F:\我的项目"
& $lifecycle resume "F:\我的项目" --json

# 检查结构、重复标识符、来源引用、测试证据和归档后的旧路径引用
& $lifecycle validate "F:\我的项目" --json

# 发布或交接时把兼容性警告也视为失败
& $lifecycle validate "F:\我的项目" --strict --json

# 包含归档资料
& $lifecycle status "F:\我的项目" --include-archive

# 归档已完成的全部工作项（或只归档指定一个）
& $lifecycle archive "F:\我的项目"
& $lifecycle archive "F:\我的项目" --work WORK-003 --json
```

## 入口如何组合

| 入口 | 作用 | 对应生命周期能力 |
| --- | --- | --- |
| `init` | 初始化目标项目资料工作区 | 项目接入 |
| `brief` | 只输出活动工作项、阻塞和下一步（约 2–3 KB） | 每轮状态查询（默认） |
| `status` | 完整清单：阶段、签署、依赖、预算与全部提示 | 状态恢复 |
| `resume` | 输出可恢复上下文和接力提示 | 跨会话接力 |
| `validate` | 检查工件、来源、证据和归档引用，保留兼容性警告 | 日常交接检查 |
| `validate --strict` | 在上述检查基础上把警告视为失败 | 发布前质量门槛 |
| `approve` | 把用户确认盖章成带审批人和时间的签署记录 | 审批签署 |
| `approve --artifact all` | 一次签完已存在的阶段工件，逐个盖章 | 整版确认 |
| `archive` | 把已完成工作项移进 `changes/archive/` | 完成收尾 |

`brief` 是每轮恢复的默认入口：完整 `status` 在 16 个工作项的项目上约 225 KB，而 `brief` 只保留筛选后的活动项与真正阻塞。每项里 `warnings` 是真阻塞（上游未批准、依赖未完成、证据缺口），`hygiene` 是整理项（文档体积、任务状态格式），`advice` 是计划质量建议（如缺 `## 评审焦点`）——只有 `warnings` 会阻止自动恢复。

`status` 与 `resume` 的 JSON 里，`state_evidence.code_sync` 区分四种情况：`verified`（报告绑定当前 HEAD 且工作区没有源码改动）、`drift`（报告覆盖到它绑定的提交，之后仓库继续改）、`stale`（锚点之后已提交源码改动，需要重新验证）、`unknown`（报告没绑提交）。`drift` 不推翻当时的结论，但也**不**当作"现在仍然成立"。

这借鉴了 Superpowers 的组合方式：每个动作有清晰边界，但仍由一个生命周期 Skill 统一处理事实、批准和漂移。用户侧风险模式是 `lite`、`managed`、`strict`；`compact`、`full` 是写入工件的兼容工作流字段，需求深挖写在 `requirements.md` 里，不是重复安装的 Skill。

## 变更历史与提交边界

变更历史以 Git 提交为准：每次实际修改后产出一个本地 commit，提交信息写清改了什么、涉及哪个 `WORK-*` 以及关键决策，Git 本身就是可回滚的事实源。Skill 不维护单独的按轮更新历史文件；需要人读的决策理由写进工作项工件（`proposal.md`、`design.md`）或 `.agent/notes/`。

本地 commit 只是恢复和回滚检查点。切换工作项或完成沉淀前先 `git status --porcelain` 确认工作区干净；`git push`、远端分支、tag 和部署不会由 Skill 自动执行，必须由用户明确授权。

可组合命令示例：

```powershell
# 提交本轮修改（提交信息带工作项编号和改动摘要）
git -C "F:\我的项目" add -A
git -C "F:\我的项目" commit -m "feat: WORK-003 调整会话超时处理"

# 用户确认需求后盖章：写入审批人、角色和脚本时间戳
# --by 可省略，省略时取 .agent/rules/always.md 的 approver；都没有时报错而不是猜
& $lifecycle approve "F:\我的项目" --work WORK-003 --artifact requirements --by "张三" --role "产品"

# 用户一次确认整版：签完已存在的需求/方案/设计/任务，逐个盖章
& $lifecycle approve "F:\我的项目" --work WORK-003 --artifact all --by "张三" --role "产品"

# 用户验收通过后登记业务验收（只接受 status: passed 的报告）
& $lifecycle approve "F:\我的项目" --work WORK-003 --artifact test-report --by "李四"

# 切换工作项前确认没有未提交改动
git -C "F:\我的项目" status --porcelain
```

## 发布前检查

维护者发布 Skill 时运行（用户不需要执行这组内部检查）：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q skills/project-lifecycle/scripts
python "<Skill 发现目录>\.system\skill-creator\scripts\quick_validate.py" "skills/project-lifecycle"
git diff --check
```

## 教程站本地运行

```powershell
npm install
npm run docs:dev
```

生产构建和预览：

```powershell
npm run docs:build
npm run docs:preview
npm run docs:serve
```

`docs:serve` 是维护者使用的本地预览服务；普通用户只需访问已部署的教程地址。

## GitHub 版本发布

当前基线是 `v0.0.2`（`v0.0.1` 是首个发布基线）。后续版本沿用标准 GitHub 流程：在 `main` 上完成回归检查 -> 创建不可移动的版本 tag -> 推送 `main` 和 tag -> 创建 GitHub Release。示例：

```powershell
git tag -a v0.0.2 -m "v0.0.2"
git push origin main
git push origin v0.0.2
```

版本号按兼容性递增；不兼容的 `.agent/` 结构、状态语义或初始化行为要在 Release 中写明迁移和回滚方式。创建 tag 前先完成测试、Skill 校验和 `git diff --check`；公开 tag 不移动、不覆盖。

## 稳定 JSON

状态和严格校验 JSON 都带 `schema_version` 与 `generated_at`。集成脚本应按 `resume.mode`、`git.status`、`source_coverage.status`、`test_evidence.status` 和 `errors`/`warnings` 字段处理，不要解析文本输出。

`resume --json` 选中工作项时还提供 `resume.work_item.goal`、`acceptance_criteria`、`constraints`、`goal_status`、`state_evidence` 和 `document_budget`。这些字段来自 `requirements.md`、已记录测试和 Git 快照，用于上下文压缩后的恢复；`state_evidence.code_sync` 为 `verified`、`stale`、`unknown` 或 `invalid`，只有 `verified` 才表示验证报告锚定的代码提交之后没有源码改动且当前工作区干净。缺失内容只会进入 `resume.warnings`，不会从聊天摘要推断。
