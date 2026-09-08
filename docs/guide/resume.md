# 跨会话恢复与接力

恢复不是把旧聊天记录搬进新聊天，而是重新读取项目里的事实，再继续当前阶段。用户只需要记住项目和 `WORK-*` 编号。

## 恢复探针

在新对话或上下文压缩后先运行：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --resume --json
```

结果中的 `resume.mode` 有三种：

| 模式 | 含义 | 下一步 |
| --- | --- | --- |
| `auto_resume` | 唯一活动工作项，阶段门槛、依赖和工作区没有已知阻塞 | 读取建议路径后继续当前阶段 |
| `ask_user` | 有多个候选，或存在审批、依赖、来源覆盖、Git 归因等阻塞 | 先选择工作项或处理阻塞 |
| `out_of_scope` | 没有未完成工作项、编号已归档，或当前路径只是外层导航工作区 | 创建新工作项或切换到真实项目 |

恢复结果还会给出：

- 当前 `WORK-*`、中文名称、阶段、状态和下一步；
- `blockers`：不能静默绕过的阻塞；
- `read_paths`：恢复前应该读取的规则和工件；
- `handoff_prompt`：可以直接粘贴到新对话的接力句；
- `git`：分支、改动数量和归因状态。

JSON 顶层还带 `schema_version` 和 `generated_at`。脚本集成应读取字段和枚举，不要依赖中文文本或输出顺序。

## 多个活动工作项

如果同时有多个未完成工作项，不能按目录时间、Git 最近修改时间或最近聊天猜测。先列候选，再明确指定：

```powershell
python "$env:USERPROFILE\.codex\skills\project-lifecycle\scripts\project_status.py" "F:\我的项目" --work WORK-003 --resume
```

也可以直接说：

```text
$project-lifecycle 在当前项目继续 WORK-003，先恢复规范和状态，再按当前阶段执行。
```

## Git 改动归因

恢复输出看到 Git 为 dirty 时，在对应工作项下创建或更新 `workspace.md`，逐项处理：

| 归类 | 处理方式 |
| --- | --- |
| 当前工作项改动 | 对照 `tasks.md` 和受影响路径，记录它属于哪项任务 |
| 用户已有改动 | 保留原样，不覆盖、不代替用户提交 |
| 未知改动 | 停止实现或清理，先让用户确认归属 |

最小归因文件：

```markdown
---
base_commit: <当前基准 commit>
---

## 工作区归因

| 路径 | 归属 | 说明 |
| --- | --- | --- |
| src/login.ts | current_work | TASK-001 的实现 |
| README.md | user_existing | 用户原有未提交修改 |
```

只有每条 Git 改动都出现在表格中、归属值有效、说明不为空且 `base_commit` 与当前 HEAD 匹配时，恢复探针才会把归因标为 complete。脏工作区不是失败，但它不能被自动当成“任务完成”或“验证通过”。Git 无法读取时按未知处理，并人工核对。

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
