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

# 包含归档资料
& $lifecycle status "F:\我的项目" --include-archive
```

## 入口如何组合

| 入口 | 作用 | 对应生命周期能力 |
| --- | --- | --- |
| `init` | 初始化目标项目资料工作区 | 项目接入 |
| `status` | 查看阶段、依赖、阻塞和 Git 归因 | 状态恢复 |
| `resume` | 输出可恢复上下文和接力提示 | 跨会话接力 |
| `validate` | 严格检查工件、来源、证据和归因 | 发布前质量门槛 |
| `history` | 生成核心组件历史视图 | 可追溯性 |

这借鉴了 Superpowers 的组合方式：每个动作有清晰边界，但仍由一个生命周期 Skill 统一处理事实、批准和漂移。`compact`、`full`、需求深挖和 HTML 理解材料是模式或按需参考，不是重复安装的 Skill。

## 核心历史

为项目声明的核心组件生成确定性的 Git 历史视图：

```powershell
& $lifecycle history `
  --config ".agent/core-components.json" `
  --output ".agent/history/core-components.md"
```

配置格式和改名规则见[总索引](/reference/)中的“Git 历史视图”条目。

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

## 稳定 JSON

状态和严格校验 JSON 都带 `schema_version` 与 `generated_at`。集成脚本应按 `resume.mode`、`git.status`、`source_coverage.status`、`test_evidence.status` 和 `errors`/`warnings` 字段处理，不要解析文本输出。
