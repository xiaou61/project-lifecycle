# Testing And Verification

Use this reference after implementation to plan and record verification against the approved upstream boundary and acceptance criteria. `strict`/`full` mode also uses the approved design; `managed`/`compact` mode does not require a separate design.

验证强度由本次改动和验收标准决定，不由 `strict` 标签机械放大。`strict` 主要增加工件、审批和证据门槛；仍然只运行能够证明本次行为的最窄可信检查，除非用户或已批准计划要求扩大范围。

## Test Plan

Create `<artifact-root>/testing/plan.md` with the same `work_id` and Chinese `work` name as the upstream artifacts. Use `artifact: test-plan` and `status: draft | ready | stale` in frontmatter. Include only relevant test levels and checks:

```markdown
# <工作项>测试计划

## 测试范围
## 环境与前置条件
## 验收矩阵
## 自动化检查
## 人工检查
## 回归范围
## 已知缺口
```

The acceptance matrix maps each `AC-*` criterion to an executable test, a manual inspection, or an explicit gap. Name the intended test location or command when known. Test externally observable behavior and meaningful contracts rather than document wording or implementation trivia.

Before running the plan, confirm that the required upstream artifacts are approved rather than `draft` or `stale`: `full` mode requires requirements, proposal, design and task plan; `compact` mode requires requirements and task plan. This is an execution precondition, not a separate user approval of the test plan. If any upstream artifact changes materially after a result is recorded, mark the report `stale` and rerun the affected checks; a previously passing command is not evidence for changed behavior.

Place executable tests in the repository's established unit, integration, end-to-end, or other test directories. Do not place executable tests under the documentation artifact root unless that is already the repository convention.

## Verification Report

Run the narrowest checks that provide credible evidence for the affected behavior, then broaden only when the change reaches shared or cross-system behavior. Record the same `work_id` and Chinese `work` name with `artifact: test-report` and `status: passed | partial | failed | stale` in frontmatter. Record the exact commands or manual procedures actually performed and their outcomes in `<artifact-root>/testing/report.md`:

```markdown
# <工作项>验证报告

## 验证环境
## 验证结果
## 验收结果
## 失败与未验证项
## 剩余风险
```

Distinguish `passed`, `failed`, and `not run`. Do not infer success from code inspection when execution is required, and do not hide unavailable infrastructure, credentials, flaky results, or environmental limitations. A partial or failed report is still useful evidence; it is not completion. `passed` is test evidence and does not by itself mean user business acceptance or release.

### 冒烟测试是可选项

默认不安排额外的冒烟测试。普通任务只执行验收矩阵中能证明本次变更的最窄可信检查，不因为使用了 `full`、`compact` 或 `validate` 就自动增加一轮通用冒烟流程。

只有以下情况才执行冒烟测试：用户明确要求；项目常驻规则明确要求；或已批准的测试计划把它列为验收项。执行时在测试计划和验证报告中写明范围、入口、预期结果和证据位置。部署任务中的健康检查或页面探测属于部署验证，不应倒推为所有开发任务的默认冒烟测试。

如果要把报告作为完成结算依据，在 frontmatter 中增加 `evidence: required`，并在“验证结果”或“检查证据”章节提供结构化矩阵：

```markdown
| 检查项 | 命令 | 退出码 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| AC-001 | `pytest tests/test_login.py -q` | 0 | passed | `testing/logs/login.txt` |
```

每个 `AC-*` 都必须出现在至少一行，命令、退出码（人工检查可写 `manual`）、结果和证据位置都不能为空；只写 `status: passed` 而没有这些信息时，严格校验不能通过。
