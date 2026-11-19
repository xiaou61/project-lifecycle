# 跨会话恢复与接力

恢复不是把旧聊天记录搬进新聊天，而是重新读取项目里的事实，再继续当前阶段。用户只需要记住项目和 `WORK-*` 编号。

## 恢复探针

在新对话或上下文压缩后先运行：

```powershell
$lifecycle = "<已安装 Skill 目录>/project-lifecycle/scripts/project-lifecycle.ps1"   # macOS/Linux 用 project-lifecycle.sh
& $lifecycle resume "F:\我的项目" --json
```

结果中的 `resume.mode` 有三种：

| 模式 | 含义 | 下一步 |
| --- | --- | --- |
| `auto_resume` | 唯一活动工作项，阶段门槛、依赖和工作区没有已知阻塞 | 读取建议路径后继续当前阶段 |
| `ask_user` | 有多个候选，或存在审批、依赖、来源覆盖等阻塞 | 先选择工作项或处理阻塞 |
| `out_of_scope` | 没有未完成工作项、编号已归档，或当前路径只是外层导航工作区 | 创建新工作项或切换到真实项目 |

当返回 `work_item` 时，恢复包还会从该工作项的 `requirements.md` 原文提取当前任务事实：

- `goal`：`## 目标` 中的目标正文；
- `acceptance_criteria`：`## 验收标准` 中包含 `AC-*` 的列表行；
- `constraints`：`## 约束与依赖` 中的列表行；
- `goal_status`：`present` 或 `missing`；
- `warnings`：目标或验收标准缺失等恢复风险。
- `state_evidence`：说明状态来自工件、已记录测试和 Git 快照。`code_sync` 为 `verified`、`stale`、`unknown` 或 `invalid`；只有验证报告声明的 `verified_commit` 之后没有源码改动、当前工作区干净时才是 `verified`，因此报告本身可以在代码提交后再提交。
- `document_budget`：核心 Markdown 的文件数和字节数软检查；超限只警告，不删除内容。

示例：

```json
{
  "resume": {
    "mode": "auto_resume",
    "work_item": {
      "work_id": "WORK-003",
      "goal": "登录成功后进入首页",
      "acceptance_criteria": ["- AC-001：登录成功后进入首页"],
      "constraints": ["- 不修改现有登录接口"],
      "goal_status": "present"
    },
    "warnings": []
  }
}
```

这些字段是恢复提示，不是新的状态数据库。`documented_state` 只表示工件推导状态，不等于源码实时完成度；测试报告没有锚点、提交变化或工作区变脏时，`code_sync` 不会是 `verified`，并要求重新核对。上下文压缩后仍要按 `read_paths` 重新读取 `always.md`、`requirements.md` 和当前阶段工件，并核对 `tasks.md`、Git 差异和实际测试；`requirements.md` 缺少目标或验收标准时，Skill 只提示缺口，不从旧聊天或摘要中臆造内容。

恢复结果还会给出：

- 当前 `WORK-*`、中文名称、阶段、状态和下一步；
- `blockers`：不能静默绕过的阻塞；
- `read_paths`：恢复前应该读取的规则和工件；
- `handoff_prompt`：可以直接粘贴到新对话的接力句；
- `git`：分支和改动数量。

JSON 顶层还带 `schema_version` 和 `generated_at`。脚本集成应读取字段和枚举，不要依赖中文文本或输出顺序。

## 多个活动工作项

如果同时有多个未完成工作项，不能按目录时间、Git 最近修改时间或最近聊天猜测。先列候选，再明确指定：

```powershell
$lifecycle = "<已安装 Skill 目录>/project-lifecycle/scripts/project-lifecycle.ps1"   # macOS/Linux 用 project-lifecycle.sh
& $lifecycle resume "F:\我的项目" --work WORK-003
```

也可以直接说：

```text
$project-lifecycle 在当前项目继续 WORK-003，先恢复规范和状态，再按当前阶段执行。
```

## Git 改动归属

恢复输出看到 Git 为 dirty 时，不要把它自动当成当前工作项的改动：属于当前工作项的对照 `tasks.md` 和受影响路径确认；用户已有的保留原样，不覆盖、不代替用户提交；未知改动先让用户确认归属，再实现或清理。脏工作区本身不是失败，但不能被当成“任务完成”或“验证通过”。

## 接力句

通用接力句：

```text
$project-lifecycle 继续 WORK-003，先恢复规范和状态，再按当前阶段执行。
```

如果想明确只继续实现：

```text
$project-lifecycle 在当前项目继续实施 WORK-003。先恢复规范和状态；满足实施门槛就按已批准任务计划改代码并测试，否则告诉我还缺什么确认。
```

`WORK-*` 只是定位键，不是批准命令。新对话仍然必须重新读取规则、状态、依赖和当前工件。

## 三四个对话同时改一个项目怎么办

目前已经解决的是恢复和防串项：每个工作项有稳定的 `WORK-*` 编号，多个活动项时恢复命令会进入 `ask_user`，不会根据最近聊天、目录时间或 Git 最近修改时间替你猜；脏工作区里的未知改动也不能算到当前工作项头上。没有解决的是同一目录里的实时并发写入，Skill 没有文件锁，也不会自动合并两个对话的修改。

最安全的安排是“一项工作，一个分支，一个 Worktree，一个写入对话”。恢复结果里的 `worktree.decision` 有三种值：已在 worktree 内是 `active`，工作区干净是 `proceed`（直接实施，不再询问），工作区有未提交改动是 `ask_user` 才需要问一次要不要开独立 worktree。创建前确认该工作项的 `.agent/changes/WORK-*/` 已提交，否则新目录里看不到需求与任务文件：

```powershell
git worktree add "..\我的项目-WORK-003" -b "work/WORK-003"
```

在新目录的对话中只执行 `WORK-003`，其他对话使用各自的 `WORK-*` 和 Worktree。完成后先在各自目录验证，再由一个整合对话查看 `git diff`、运行 `project-lifecycle.ps1 validate` 和回归测试，最后合并分支。若只能共用一个目录，约定同一时刻只有一个对话可以写入；其他对话只读或等待，并在切换前运行：

```powershell
git -C "F:\我的项目" status --porcelain
```

看到大量未提交改动、无法归类的新文件或多个活动工作项时，不要让新对话直接改代码；先指定 `--work WORK-xxx`，或请用户确认未知改动归属。这样能防止错误接力，但不能替代 Git 分支合并和人工冲突处理。
