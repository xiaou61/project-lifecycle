# Testing And Verification

Use this reference after implementation to plan and record verification against the approved upstream boundary and acceptance criteria. `strict`/`full` mode also uses the approved design; `managed`/`compact` mode does not require a separate design.

验证强度由本次改动和验收标准决定，不由 `strict` 标签机械放大。`strict` 主要增加工件、审批和证据门槛；仍然只运行能够证明本次行为的最窄可信检查，除非用户或已批准计划要求扩大范围。

## 完成前的硬门

**没有新鲜的验证证据，不许声称完成。** 这不是风格建议，是四步顺序：

1. **确定命令**：哪条命令能证明这个结论？想不出命令，说明这个结论还不能声称。
2. **跑完整命令**：全新执行，不复用上一轮结果、不跑一个"差不多的"子集。
3. **读完整输出**：看退出码、数失败数、看跳过数。只看"BUILD SUCCESS"不算读了输出。
4. **输出确实支持结论**，才能说通过。输出与结论对不上时，结论错，不是输出错。

以下说法一律不算证据：`应该能过`、`我很有信心`、`刚才跑过类似的了`、`lint 过了所以构建没问题`、`子代理说成功了`、`只跑了一半`。含糊措辞（`应该`、`大概`、`看起来`）出现在完成声明里，本身就是漏了这一步的信号。

不同结论需要的证据不同，不能互相顶替：

| 你要说的结论 | 必须跑的命令 | 看到什么才算成立 |
| --- | --- | --- |
| 测试通过 | 完整测试命令 | 0 failed；skipped 单独计数并说明原因 |
| 构建成功 | 构建命令 | 退出码 0，且不是"跳过了构建" |
| 类型检查/lint 干净 | 检查命令 | 0 errors |
| 修好了某个缺陷 | 原症状用例 + 去掉修复再跑一次 | 先红后绿（反向验证） |
| 需求/验收满足 | 逐条对照 `AC-*` | 每条都有对应证据行 |
| 子代理或他人说完成 | 看实际 diff 与命令输出 | 不以"它说完成了"为准 |

**跳过（skipped）不等于通过。** 测试按条件跳过时退出码仍是 0；必须单独数 skipped 列并说明为什么跳过。项目若用"未配置就跳过"的集成测试写法，任何一次绿色构建都可能一条真实用例都没跑。

**修缺陷要反向验证。** 修 bug 的证据不是"现在过了"，而是"去掉修复后原症状的用例确实红"（red-green 已实测）。没做反向验证的修复，可能只是把测试写成了对照新行为。

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

业务验收是另一个事实，写在同一份报告的 frontmatter 里：用户明确验收通过后运行 `project-lifecycle.ps1 approve --work WORK-003 --artifact test-report --by "李四"`，写入 `accepted_by` 和 `accepted_at`（见 [workflow.md](workflow.md) 的“签署”）。它只登记验收，不改报告的 `status`，也不替代 `passed`；报告不是 `passed` 时拒绝登记。没有验收记录时报告仍然是有效的测试证据，只是完成结算还差用户验收。

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
