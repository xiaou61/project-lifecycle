# Proposal

Use this reference to choose what will be built and why. A proposal is a decision document between requirements and detailed design.

## Preconditions

- Read the current `requirements.md` and relevant repository architecture.
- Require approved requirements unless the user approves them while requesting the proposal.
- If repository evidence contradicts a requirement or makes it infeasible, surface that conflict before recommending an approach.

## Proposal Artifact

Use these sections when relevant:

```markdown
# <工作项>提案

## 摘要
## 推荐方案
## 范围
## 备选方案
## 仓库影响
## 交付拆分
## 风险与缓解措施
## 验收映射
## 待决定事项
```

The recommended approach should explain the essential mechanism, affected ownership areas, and why it best satisfies the requirements. Record only genuine alternatives, including the status quo when it was a credible option. State what each alternative buys and why it was not selected.

Keep detailed class names, schemas, payloads, and file-by-file changes for the design unless they are necessary to establish feasibility. Do not present estimates as facts without evidence.

Map the proposal to requirement and acceptance identifiers so omissions are visible. Keep the proposal at `status: draft` until the user explicitly approves the selected approach and any material open decisions.

Do not add product scope in the proposal. When the recommended approach requires behavior absent from the requirements, revise and reapprove the requirements first. A materially changed approved proposal makes the current design, task plan, and verification artifacts `stale`.
