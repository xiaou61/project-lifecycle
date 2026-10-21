# managed 最小走查

一个普通功能从需求到验证的完整路径。`strict` 只多出 proposal 和 design 两步，字段写法相同，见各自的参考文件。

## 1. 初始化与状态

```powershell
$lifecycle init "F:\示例项目"
& $lifecycle brief "F:\示例项目" --json
```

`brief` 此时返回 `NONE` 态和 `next_action: 创建需求`。初始化只增加 `.agent/`，不改源码。

## 2. 需求：只写会改变交付结果的事

`requirements.md` 由 Agent 起草、用户确认后才批准。`mode_reason` 要写具体理由。

```markdown
---
artifact: requirements
work_id: WORK-001
work: 导出订单 CSV
status: draft
mode: managed
mode_reason: 跨前后端两个模块，需要跨会话继续，但不改变公共接口
workflow: compact
created: 2026-10-21
updated: 2026-10-21
---

# 导出订单 CSV 需求

## 目标

运营可以在订单列表页导出当前筛选结果为 CSV。

## 验收标准

- AC-001 导出内容与当前筛选条件一致，含表头。
- AC-002 超过 50,000 行时提示分批导出，不阻塞页面。

## 约束

- 复用现有 `OrderQueryService`，不新增查询入口。
```

用户说“这版需求确认”后：

```powershell
& $lifecycle approve "F:\示例项目" --work WORK-001 --artifact requirements --by "张三" --role "运营"
```

签署字段由脚本盖，Agent 不手填。

## 3. 任务：一个步骤一个可检查结果

```markdown
---
artifact: tasks
work_id: WORK-001
work: 导出订单 CSV
status: draft
created: 2026-10-21
updated: 2026-10-21
---

# 导出订单 CSV 实施任务

## TASK-001 | 导出接口返回 CSV

- 对应：AC-001
- 依赖：无
- 步骤：写失败测试 -> 跑红 -> 最小实现 -> 跑绿
- 完成判据：`pytest tests/test_export.py -q` 退出码 0

## TASK-002 | 行数上限提示

- 对应：AC-002
- 依赖：TASK-001
- 完成判据：构造 50,001 行数据时返回提示且响应时间 < 2s

## 评审焦点

- 空筛选结果导出只有表头，覆盖在 TASK-001 的测试里。
- 并发导出互不污染临时文件，覆盖在 TASK-001 的测试里。
```

## 4. 实施与验证

```powershell
& $lifecycle resume "F:\示例项目" --work WORK-001 --json
```

`resume` 的返回里 `worktree.decision` 是 `ask_user`（主工作树）或 `active`（已在独立 worktree 内）。看到 `ask_user` 就先问一次：

```text
要不要为 WORK-001 开一个独立 Git worktree？
- 开：在新分支 work/WORK-001 上工作，目录 ..\示例项目-WORK-001，不影响当前目录的改动
- 不开：直接在当前目录工作，同一时刻只允许一个写入对话
```

用户同意再执行，并记录这次决定：

```powershell
git worktree add "..\示例项目-WORK-001" -b "work/WORK-001"
& $lifecycle record "F:\示例项目" --work WORK-001 --type decision `
  --decision "WORK-001 使用 worktree：..\示例项目-WORK-001，分支 work/WORK-001"
```

开之前确认该工作项的 `.agent/changes/WORK-001-*/` 已经提交——worktree 只检出已提交内容。用户拒绝就留在当前目录，不要反复再问。

按 `tasks.md` 逐项改代码，每项完成后同步任务状态。验证写进 `testing/report.md`：

```markdown
---
artifact: test-report
work_id: WORK-001
work: 导出订单 CSV
status: passed
evidence: required
---

# 导出订单 CSV 验证报告

## 验证结果

| 检查项 | 命令 | 退出码 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| AC-001 | `pytest tests/test_export.py -q` | 0 | passed | `testing/logs/pytest.txt` |
| AC-002 | 同上（`test_export_limit`） | 0 | passed | 同上 |
```

`passed` 只代表证据齐全，不代表用户验收。

## 5. 收尾

```powershell
& $lifecycle record "F:\示例项目" --work WORK-001 `
  --change "新增订单 CSV 导出" `
  --verification "pytest tests/test_export.py -q：通过"
& $lifecycle archive "F:\示例项目" --work WORK-001
& $lifecycle validate "F:\示例项目"
```

归档只移动目录、不改内容。下一轮 `brief` 不再列出这个工作项。

## 常见走偏

| 现象 | 正确做法 |
| --- | --- |
| 需求还没确认就写 `tasks.md` | 停在需求门槛，下游工件等批准 |
| 测试没跑就写 `status: passed` | 按 `references/testing.md` 的硬门要新鲜输出 |
| 任务拆成“实现整个模块” | 拆成可独立验证的纵向切片 |
| 中途接口变了仍在原任务里消化 | 回需求或设计，让下游失效 |
