# 命令参考

这些是给用户和自动化调用的稳定入口。底层 Python 文件属于 Skill 实现细节，普通用户不需要直接运行 Python。

```powershell
$lifecycle = "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project-lifecycle.ps1"
```

## 初始化

```powershell
& $lifecycle init "F:\我的项目"
```

初始化器是幂等的：已有 `AGENTS.md`、`.agent/`、源码、测试和 Git 历史会被保留。

## 状态查询

```powershell
# 当前活动工作项
& $lifecycle status "F:\我的项目"

# 按编号或中文名称查询
& $lifecycle status "F:\我的项目" --work WORK-003
& $lifecycle status "F:\我的项目" --work "用户登录"

# 恢复上下文
& $lifecycle resume "F:\我的项目"
& $lifecycle resume "F:\我的项目" --json

# 检查结构、重复标识符、来源引用、测试证据和 Git 归因
& $lifecycle validate "F:\我的项目" --json

# 发布或交接时把兼容性警告也视为失败
& $lifecycle validate "F:\我的项目" --strict --json

# 包含归档资料
& $lifecycle status "F:\我的项目" --include-archive
```

## 入口如何组合

| 入口 | 作用 | 对应生命周期能力 |
| --- | --- | --- |
| `init` | 初始化目标项目资料工作区 | 项目接入 |
| `status` | 查看阶段、依赖、阻塞和 Git 归因 | 状态恢复 |
| `resume` | 输出可恢复上下文和接力提示 | 跨会话接力 |
| `validate` | 检查工件、来源、证据和归因，保留兼容性警告 | 日常交接检查 |
| `validate --strict` | 在上述检查基础上把警告视为失败 | 发布前质量门槛 |
| `history` | 生成核心组件历史视图 | 可追溯性 |
| `push-check` | 用 `git ls-remote` 核对远端提交和更新历史 | 推送后核验 |

这借鉴了 Superpowers 的组合方式：每个动作有清晰边界，但仍由一个生命周期 Skill 统一处理事实、批准和漂移。用户侧风险模式是 `lite`、`managed`、`strict`；`compact`、`full` 是写入工件的兼容工作流字段，需求深挖和 HTML 理解材料按需读取，不是重复安装的 Skill。

## 核心历史

为项目声明的核心组件生成确定性的 Git 历史视图：

```powershell
& $lifecycle history `
  --config ".agent/core-components.json" `
  --output ".agent/history/core-components.md"
```

配置格式和改名规则见[总索引](/reference/)中的“Git 历史视图”条目。

## 更新历史与提交边界

初始化后，目标项目会有 `.agent/history/updates.md`。每次实际修改后追加本轮的变更、决策、依据、验证和提交状态；新记录标题精确到秒并带本地时区，例如 `2026-09-09 14:32:07 +0800`。详细字段见 [更新历史规则](https://github.com/xiaou61/project-lifecycle/blob/main/skills/project-lifecycle/references/update-history.md)。

本地 commit 只是恢复和回滚检查点。切换工作项或完成沉淀前应先完成本地检查点；`git push`、远端分支、tag 和部署不会由 Skill 自动执行，必须由用户明确授权。

可组合命令示例：

```powershell
# 查看最近 10 条更新
& $lifecycle updates "F:\我的项目" --tail 10

# 追加一条结构化更新记录
& $lifecycle record "F:\我的项目" --work WORK-003 --title "修复登录超时" --type implementation `
  --change "调整会话超时处理" --decision "保留现有接口" --basis ".agent/changes/WORK-003-登录/design.md" `
  --verification "pytest tests/test_login.py -q：通过"

# 切换工作项前检查是否还有未提交改动；有改动时返回非零
& $lifecycle checkpoint "F:\我的项目" --json

# 推送后核对远端 HEAD 是否已同步，及 updates.md 是否记录
& $lifecycle push-check "F:\我的项目" --json

# 核验成功后追加本地远端记录（不会提交或再次推送）
& $lifecycle push-check "F:\我的项目" --record-push --work WORK-003
```

## 发布前检查

维护者发布 Skill 时运行（用户不需要执行这组内部检查）：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q skills/project-lifecycle/scripts
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" "skills/project-lifecycle"
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

当前基线是 `v0.0.1`。后续版本沿用标准 GitHub 流程：功能或修复分支 -> 回归检查 -> 合并 `main` -> 创建不可移动的版本 tag -> 推送 `main` 和 tag -> 创建 GitHub Release。示例：

```powershell
git tag -a v0.0.2 -m "v0.0.2"
git push origin main
git push origin v0.0.2
```

版本号按兼容性递增；不兼容的 `.agent/` 结构、状态语义或初始化行为要在 Release 中写明迁移和回滚方式。创建 tag 前先完成测试、Skill 校验、更新历史和 `git diff --check`；公开 tag 不移动、不覆盖。

## 稳定 JSON

状态和严格校验 JSON 都带 `schema_version` 与 `generated_at`。集成脚本应按 `resume.mode`、`git.status`、`source_coverage.status`、`test_evidence.status` 和 `errors`/`warnings` 字段处理，不要解析文本输出。

`resume --json` 选中工作项时还提供 `resume.work_item.goal`、`acceptance_criteria`、`constraints`、`goal_status`、`state_evidence` 和 `document_budget`。这些字段来自 `requirements.md`、已记录测试和 Git 快照，用于上下文压缩后的恢复；`state_evidence.code_sync` 为 `verified`、`stale`、`unknown` 或 `invalid`，只有 `verified` 才表示验证报告锚定的代码提交之后没有源码改动且当前工作区干净。缺失内容只会进入 `resume.warnings`，不会从聊天摘要推断。
