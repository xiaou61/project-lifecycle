---
name: project-lifecycle
description: 通过稳定项目规格、按工作项的需求/提案/设计/任务/验证资料和可检索长期记忆，引导重要软件工作从澄清到交付并控制项目漂移；不用于无需生命周期文档的孤立小改动。
---

# Project Lifecycle

Treat repository artifacts, not chat history, as the durable source of project state. Keep the workflow proportional to the work: a small change may need short artifacts, while a broad project may need more detail. Do not invent sections, infrastructure, or future flexibility that the work does not require.

## Output Language

Use Simplified Chinese by default for user-facing conversation and every artifact created by this skill, including headings, explanations, decisions, test plans, verification reports, and generated history labels. Preserve source-code identifiers, file paths, commands, requirement and acceptance IDs, machine-readable status values, and verbatim Git commit subjects. Switch languages only when the user explicitly requests it or the target repository has a mandatory language rule; surface that repository constraint when it conflicts with the default.

## Operating Model And Initialization

Use a two-part operating model:

1. The reusable Skill package contains workflow instructions, phase references, and deterministic helpers.
2. The target project's `.agent/` workspace contains that project's durable lifecycle state: current specs, active changes, memory, references, decisions, and evidence.

GitHub, a local checkout, a plugin, and a Codex discovery directory are distribution or installation mechanisms for the same Skill package; they are not separate runtime layers. Never copy the whole Skill package into `.agent/`. The source repository being present somewhere on disk does not by itself make the Skill available: Codex must discover or explicitly load it.

Before the first managed work item in a project, run [scripts/init_project.py](scripts/init_project.py) against the project root. The initializer creates a root `AGENTS.md` when missing, then creates `.agent/`, `.agent/specs/`, `.agent/changes/`, the shared knowledge directories, `.agent/memory.md`, a short workspace guide, and a copy of the deterministic core-history generator. It preserves existing files and is safe to run again. It never overwrites `AGENTS.md`, `AGENTS.override.md`, or existing `.agent/` files.

The generated root `AGENTS.md` is an optional project adapter: it tells Codex when to use `$project-lifecycle` and where project artifacts live. It does not install or discover the Skill. If a root `AGENTS.override.md` exists, mention that it takes precedence over the generated base rules.

When an `AGENTS.md` already exists, preserve it without appending or rewriting. Report that the lifecycle routing rules were not merged and ask the user to confirm the existing instructions cover them. When legacy `.agent/project/` or `.agent/features/` directories exist, preserve them and report the manual migration mapping; never move project records automatically.

## Locate The Work

1. Read the applicable repository instructions and inspect existing documentation before creating anything.
2. Identify the current work item and phase from the user's request and existing artifacts. Resume existing artifacts instead of replacing them.
3. Decide whether the work needs persisted lifecycle artifacts. An isolated, low-risk fix may proceed without a `.agent/changes/` entry; a new project, important feature, cross-module change, public behavior change, migration, or work likely to span sessions should use one.
4. Follow an established repository location when one exists. Otherwise use `.agent/changes/<work-slug>/` for every managed work item, including whole-project inception. Scale document depth to the work; do not create separate directory systems for projects and features.
5. Create only the artifact needed for the current phase. Do not scaffold empty later-phase files.

Use `.agent/specs/` only for stable, reusable statements about how the project should behave today: cross-feature contracts, domain rules, architecture boundaries, or operational invariants. Do not copy every feature's temporary proposal there. Read [references/specs.md](references/specs.md) when creating, updating, reconciling, or archiving stable specs.

Use this default artifact set:

```text
<artifact-root>/
  requirements.md
  proposal.md
  design.md
  tasks.md
  testing/
    plan.md
    report.md
```

Executable tests remain in the repository's normal test directories. The `testing/` folder contains the test plan and recorded verification evidence, not duplicate test source.

## Stable Project Specs

`.agent/specs/` is the current-project view: concise statements of behavior and constraints that remain useful after an individual change is finished. It is optional for a tiny project and should grow only when a fact is shared or repeatedly needed. It is not a dump of all source code and it is not a replacement for executable tests.

An active change in `.agent/changes/<work-slug>/` explains what is being proposed. After implementation and verification, reconcile affected stable specs, then move the completed change to `.agent/changes/archive/<date>-<work-slug>/` when the repository wants an audit trail. Preserve the change in Git; do not delete it or rewrite it into an opaque summary. If no stable project fact changed, leave `specs/` untouched.

## Project Memory

Use `.agent/memory.md` as a compact index of durable knowledge that should influence future work across tasks. Before a substantial task, list its entry headings and search for terms related to the affected feature, module, paths, constraints, and technologies. Read only the matching entries and enough surrounding context to interpret them; read the entire file only when it is small or the task is repository-wide.

Read [references/memory.md](references/memory.md) before adding, changing, invalidating, or compacting memory entries. Store only evidence-backed knowledge that is likely to matter beyond the current task. Memory is a discovery aid, not authority over approved lifecycle artifacts, current code, tests, or Git. When they conflict, verify the authoritative source and mark or replace the memory entry instead of silently following it.

## Approval Gates

- Never mark an artifact approved on the agent's own authority. Approval must be explicit in a user message.
- Requirements precede the proposal, an approved proposal precedes design, an approved design precedes task planning, and an approved task plan precedes implementation. The user may explicitly waive or combine a gate.
- A request to draft the next artifact is not approval of the current one unless the user clearly says both.
- Keep unresolved decisions visible. Do not silently convert assumptions into requirements.
- If implementation reveals a material change to scope, architecture, public behavior, data, security, or migration, revise the affected artifact and obtain approval before continuing. Record minor implementation detail without reopening the gate.

For `requirements.md`, `proposal.md`, `design.md`, and `tasks.md`, use concise YAML frontmatter:

```yaml
---
work: <slug>
artifact: requirements | proposal | design | tasks
status: draft | approved | stale
updated: YYYY-MM-DD
---
```

Keep approval evidence in prose near the status or in version control; do not create a separate workflow database.

Use `draft | approved` for requirements, `draft | approved | stale` for proposals, designs, and task plans, and `passed | partial | failed | stale` for verification reports. `stale` means an upstream material change invalidated the artifact; it is never an approval state. Preserve an existing `feature:` field when resuming an older artifact; use `work:` for new artifacts and do not perform metadata-only migrations.

## Control Drift

Treat approved requirements as the source of scope. Stable specs describe the current intended project behavior; a proposal chooses an approach for one change, a design explains how to build it, a task plan sequences the work, implementation realizes the plan, and verification proves the acceptance criteria. A downstream artifact must not quietly introduce a new requirement, and a stable spec must not be edited merely to make an unauthorized implementation appear correct.

When a material change appears:

1. Stop at the current phase and identify whether the change affects scope, approach, design, or only local implementation detail.
2. Update the earliest affected artifact. Return it to `draft` and obtain explicit approval.
3. Mark every affected downstream artifact `stale`; do not treat its previous approval or test result as current evidence.
4. Revise downstream artifacts in order, preserving unaffected content, and repeat the required approvals and verification.
5. Reconcile `.agent/specs/` only after implementation and verification support the new behavior.

A material change alters a goal, non-goal, acceptance criterion, chosen approach, public behavior, interface, owned data, security rule, migration, or operational requirement. Renaming a local variable or choosing an equivalent library call is normally not material.

Before advancing phases, perform a short alignment check:

- every requirement and goal is addressed by the proposal;
- every proposed responsibility is realized by the design;
- every design responsibility is covered by an executable task;
- every material code change is authorized by the approved design and task plan;
- every acceptance criterion maps to verification evidence; and
- no deliverable introduces unapproved scope or contradicts a non-goal.

If an item has no stable identifier, cite its heading or exact wording. Report mismatches before continuing. Do not declare alignment from document statuses alone; compare their content and the code.

## Route By Phase

### Requirements Discovery

Read [references/requirements.md](references/requirements.md). Discuss the need before proposing implementation. Ask only questions whose answers change scope, behavior, constraints, or acceptance. Produce or revise `requirements.md` when the user asks to capture the result or when a stable draft is useful.

### Proposal

Read [references/proposal.md](references/proposal.md). Base the proposal on the approved requirements, or on requirements the user approves in the same message. Recommend one approach, record real alternatives and tradeoffs, and keep implementation detail out unless it affects feasibility or the decision.

### Design

Read [references/design.md](references/design.md). Translate the approved proposal into an implementable design grounded in the current repository. Resolve component ownership, interfaces, data flow, failure behavior, migration, and verification only where relevant.

### Task Planning

Read [references/tasks.md](references/tasks.md). Translate the approved design into a dependency-ordered implementation checklist with exact affected paths and a verification step for each task. Keep product scope and architecture out of the task plan; if they need to change, return to the earliest affected artifact.

### Implementation

Read the approved requirements, proposal, design, and task plan before editing code. Inspect the current implementation and reuse repository conventions. Execute tasks in dependency order, update their execution state from actual work, and implement the smallest complete change that satisfies the acceptance criteria. Add or update executable tests in the repository's normal locations and keep documentation synchronized with material discoveries.

Do not mark delivery verified merely because tasks are checked off. If implementation requires a material deviation, follow the drift-control procedure before continuing. A newly discovered local step that remains inside the approved design may be added to `tasks.md` with its reason; a scope, interface, data, security, migration, or architecture change requires upstream revision and approval.

### Testing And Verification

Read [references/testing.md](references/testing.md). Create `testing/plan.md` when verification begins, run the relevant checks, and write `testing/report.md` from actual evidence. Map every acceptance criterion to a test, inspection, or explicitly unverified item.

### Alignment Audit

At any phase, the user may ask for an alignment or drift check. Compare stable specs, approved requirements, proposal, design, task plan, current implementation, executable tests, and verification report in that order. Report missing coverage, unauthorized behavior, contradictions, stale artifacts, and tests that no longer prove an acceptance criterion. Do not explain away a mismatch by editing the upstream intent after the fact; apply the change-control procedure if the user chooses to accept it.

### Core Change History

Read [references/core-history.md](references/core-history.md) when the user asks to track important classes or components across Git commits. After initialization, use the target project's `.agent/scripts/generate_core_history.py` to regenerate the Markdown projection from Git; the copy in this skill package is only the initializer's source. Git remains the authority, and the Markdown is derived and may be regenerated after amend, rebase, merge, or rollback. Do not auto-commit generated output from a Git hook.

## Completion

A work item is complete only when:

- the approved requirements, proposal, and design reflect the delivered behavior;
- the approved task plan covers the delivered work and records its actual execution state;
- implementation and executable tests are present in their normal repository locations;
- `testing/report.md` records the commands and checks actually performed;
- every acceptance criterion is passed or clearly reported as failed or unverified; and
- remaining limitations and follow-up work are explicit; and
- no artifact used as evidence is marked `draft` or `stale`.

After these checks, reconcile affected stable specs and optionally archive the completed change under `.agent/changes/archive/`. Do not mark a change complete solely because its task checkboxes are checked.

At completion, check whether the work established or invalidated durable cross-task knowledge. Update `.agent/memory.md` only when it did; do not create a memory entry merely to summarize the completed task.

Create or update a note under `.agent/notes/` only when the work establishes a cross-feature decision whose rationale should guide future changes. Do not duplicate an ordinary proposal or design there.
