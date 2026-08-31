# Work Identity And Relationships

Use this reference when creating a managed work item, querying work status, or handling two requirements that may affect each other.

## Stable Identity And Chinese Name

Every managed requirement has two identifiers with different jobs:

- `work_id`: a stable machine identifier such as `WORK-003`; it never changes and is used by relationships and queries.
- `work`: a concise Chinese name such as `用户登录`; it is what the user sees throughout discussion, design, implementation, testing, and completion.

When a new managed requirement appears:

1. Propose a short, outcome-focused Chinese name in the first orientation response. Do not ask for a name unless two materially different interpretations remain.
2. Run `scripts/project_status.py <project-root> --json` and use its `next_work_id`, which scans active and archived work items. Never guess from the visible active list and never reuse an archived number.
3. Create `.agent/changes/WORK-003-用户登录/requirements.md` during the initial requirement discussion. Record the user's original outcome and current open questions so the file is not an empty placeholder.
4. Use the same `work_id` and `work` values in the frontmatter and H1 of every artifact for that work item.
5. In user-facing status, prefer `用户登录`; include `WORK-003` when several work items exist, a relationship is discussed, or disambiguation is useful.

Use a filesystem-safe Chinese directory name. Avoid Windows-reserved characters `< > : " / \ | ? *`, trailing periods or spaces, and generic names such as “新需求”, “功能开发”, or “问题修复”. Product and technical identifiers may remain in their original spelling inside a Chinese name, for example `OAuth 登录` or `API 限流`.

Do not silently rename a persisted work item. If the user explicitly changes its meaning or name, preserve `work_id`, update the Chinese name and artifact headings consistently, and treat a material meaning change through normal drift control. Relations refer to `work_id`, so a deliberate directory rename does not break the graph.

When a new statement appears during an active work item, decide whether it changes the same outcome or introduces an independently approvable and testable outcome. Keep it in the current work item when it changes that item's scope or acceptance criteria and apply drift control. Create a new `WORK-*` item when it can be approved, delivered, and accepted independently; state the new Chinese name and whether focus is switching. If this distinction changes delivery and remains ambiguous, ask one focused question instead of silently splitting or merging.

Use this frontmatter for new lifecycle artifacts:

```yaml
---
work_id: WORK-003
work: 用户登录
artifact: requirements | proposal | design | tasks | test-plan | test-report
status: draft | approved | stale
depends_on: [WORK-001]
related_to: [WORK-002]
updated: YYYY-MM-DD
---
```

`depends_on` and `related_to` belong only in `requirements.md`; omit them from downstream artifacts. Test reports use their verification statuses instead of `draft | approved | stale`. Existing work items without `work_id` remain valid; do not perform metadata-only migrations unless the user asks.

## Two Relationship Types

Use only the relationship needed by delivery:

| Type | Meaning | Workflow effect |
| --- | --- | --- |
| `depends_on` | This work item cannot be implemented or verified correctly until another work item is complete | Hard blocker before implementation; status query shows the unfinished dependency |
| `related_to` | The work items share behavior, contracts, modules, data, or decisions, but can still be delivered independently | Does not block; requires an impact check before either item crosses a phase boundary |

Relationships use `WORK-*` IDs, not names or paths. A hard dependency is directional: if `WORK-003` depends on `WORK-001`, record it only in `WORK-003`. A soft relation is conceptually symmetric; recording it in either requirements file is enough because the status inspector resolves the reverse view.

The agent discovers and proposes these relationships by comparing the new request with active work items and stable specs; the user should not have to maintain the graph manually. State the inferred relationship and reason during requirements discussion, and let the user correct a materially wrong classification before approval.

In `requirements.md`, add a short `## 关联工作项` section explaining why each declared relationship exists and which contract, acceptance criterion, module, or decision connects them. The frontmatter is the machine-readable relationship; the section provides the rationale.

## Decide Whether To Link Or Merge

Use this order:

1. If two requests pursue the same outcome or cannot be approved and accepted independently, keep one work item and discuss the combined scope. Do not create a dependency graph to disguise one requirement as two.
2. If one request needs a concrete result from the other, keep separate work items and use `depends_on`.
3. If both can ship independently but may change shared behavior or ownership, use `related_to`.
4. If they merely touch the same file without sharing behavior or a decision, do not create a relation; file overlap alone is not a product dependency.

Do not automatically merge already approved work. Report the overlap and let the user choose the surviving scope. Preserve the retired work item's history rather than deleting it.

## Impact And Drift

Before approving, implementing, or verifying a work item with relations:

1. Query both outgoing and incoming relations.
2. Compare the shared requirements, stable specs, interfaces, data, security constraints, affected paths, and acceptance criteria.
3. If the current change materially alters something another active work item relies on, return the earliest affected artifact in that work item to `draft` and mark its downstream artifacts `stale`.
4. If there is no material impact, record that conclusion briefly in the current proposal, design, or verification report; do not edit the other work item merely because it is related.

A dependency cycle is invalid workflow state. Resolve it by combining work items that cannot be independently accepted, or by extracting their shared prerequisite into a third work item that both depend on. Do not start implementation while the cycle remains.

When several requirements define the same long-lived contract, keep the current contract in `.agent/specs/` and let each work item reference it. Do not copy the contract into every requirements document.
