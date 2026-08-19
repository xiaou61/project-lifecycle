# Testing And Verification

Use this reference after implementation to plan and record verification against the approved requirements and design.

## Test Plan

Create `<artifact-root>/testing/plan.md`. Include only relevant test levels and checks:

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

Before running the plan, confirm that its requirements, proposal, design, and task plan are approved rather than `draft` or `stale`. If any upstream artifact changes materially after a result is recorded, mark the report `stale` and rerun the affected checks; a previously passing command is not evidence for changed behavior.

Place executable tests in the repository's established unit, integration, end-to-end, or other test directories. Do not place executable tests under the documentation artifact root unless that is already the repository convention.

## Verification Report

Run the narrowest checks that provide credible evidence for the affected behavior, then broaden only when the change reaches shared or cross-system behavior. Record the exact commands or manual procedures actually performed and their outcomes in `<artifact-root>/testing/report.md`:

```markdown
# <工作项>验证报告

状态：passed | partial | failed | stale

## 验证环境
## 验证结果
## 验收结果
## 失败与未验证项
## 剩余风险
```

Distinguish `passed`, `failed`, and `not run`. Do not infer success from code inspection when execution is required, and do not hide unavailable infrastructure, credentials, flaky results, or environmental limitations. A partial or failed report is still useful evidence; it is not completion.
