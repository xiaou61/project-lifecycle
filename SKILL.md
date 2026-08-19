---
name: project-lifecycle
description: 通过持久化文档、可检索的项目长期记忆和明确审批门槛，引导软件项目或功能完成需求澄清、提案、设计、实现与验证。适用于启动或恢复重要开发工作、沉淀跨任务项目知识，以及检查交付是否偏离已批准需求；不用于无需生命周期文档的孤立小改动。
---

# Project Lifecycle

Treat repository artifacts, not chat history, as the durable source of project state. Keep the workflow proportional to the work: a small change may need short artifacts, while a broad project may need more detail. Do not invent sections, infrastructure, or future flexibility that the work does not require.

## Output Language

Use Simplified Chinese by default for user-facing conversation and every artifact created by this skill, including headings, explanations, decisions, test plans, verification reports, and generated history labels. Preserve source-code identifiers, file paths, commands, requirement and acceptance IDs, machine-readable status values, and verbatim Git commit subjects. Switch languages only when the user explicitly requests it or the target repository has a mandatory language rule; surface that repository constraint when it conflicts with the default.

## Initialize The Project

The skill is installed as a reusable package in a Codex skill discovery directory. Its root contains `SKILL.md`, `agents/`, `references/`, and `scripts/`. A target project is a separate repository or directory with its own `.agent/` workspace. Never copy the whole skill package into that `.agent/` directory.

The source repository being present somewhere on disk does not by itself make the Skill available. Codex must load it from a configured Skill discovery directory, or the user must invoke it by an explicit path while developing it.

There are three locations to keep distinct:

1. the GitHub/source repository for versioning and distribution;
2. the local installed Skill directory from which Codex loads `$project-lifecycle` (normally `$CODEX_HOME/skills/project-lifecycle` in the bundled installer environment, or another configured skill discovery directory); and
3. the target project's `.agent/` directory for project-specific requirements, decisions, memory, and verification evidence.

Before the first lifecycle operation in a project, run [scripts/init_project.py](scripts/init_project.py) against the project root. The initializer creates a root `AGENTS.md` when it is missing, then creates `.agent/`, its working subdirectories, `.agent/memory.md`, a short project-local directory guide, and a copy of the deterministic core-history generator. It preserves existing files and is safe to run again. It never overwrites `AGENTS.md`, `AGENTS.override.md`, or existing `.agent/` files.

The generated root `AGENTS.md` is a small routing layer: it tells Codex when to use `$project-lifecycle` and where project artifacts live. It does not install or discover the Skill; the Skill must already be available in a Codex Skill discovery directory. If a root `AGENTS.override.md` exists, mention that it takes precedence over the generated base rules.

When an `AGENTS.md` already exists, preserve it without appending or rewriting. Report that the lifecycle routing rules were not merged and ask the user to confirm the existing instructions cover them.

## Locate The Work

1. Read the applicable repository instructions and inspect existing documentation before creating anything.
2. Identify the current work item and phase from the user's request and existing artifacts. Resume existing artifacts instead of replacing them.
3. Follow an established repository location when one exists. Otherwise use:
   - `.agent/project/` for whole-project inception.
   - `.agent/features/<feature-slug>/` for a feature or substantial change.
4. Create only the artifact needed for the current phase. Do not scaffold empty later-phase files.

Use this default artifact set:

```text
<artifact-root>/
  requirements.md
  proposal.md
  design.md
  testing/
    plan.md
    report.md
```

Executable tests remain in the repository's normal test directories. The `testing/` folder contains the test plan and recorded verification evidence, not duplicate test source.

## Project Memory

Use `.agent/memory.md` as a compact index of durable knowledge that should influence future work across tasks. Before a substantial task, list its entry headings and search for terms related to the affected feature, module, paths, constraints, and technologies. Read only the matching entries and enough surrounding context to interpret them; read the entire file only when it is small or the task is repository-wide.

Read [references/memory.md](references/memory.md) before adding, changing, invalidating, or compacting memory entries. Store only evidence-backed knowledge that is likely to matter beyond the current task. Memory is a discovery aid, not authority over approved lifecycle artifacts, current code, tests, or Git. When they conflict, verify the authoritative source and mark or replace the memory entry instead of silently following it.

## Approval Gates

- Never mark an artifact approved on the agent's own authority. Approval must be explicit in a user message.
- Requirements precede the proposal, an approved proposal precedes design, and an approved design precedes implementation. The user may explicitly waive or combine a gate.
- A request to draft the next artifact is not approval of the current one unless the user clearly says both.
- Keep unresolved decisions visible. Do not silently convert assumptions into requirements.
- If implementation reveals a material change to scope, architecture, public behavior, data, security, or migration, revise the affected artifact and obtain approval before continuing. Record minor implementation detail without reopening the gate.

For `requirements.md`, `proposal.md`, and `design.md`, use concise YAML frontmatter:

```yaml
---
feature: <slug>
artifact: requirements | proposal | design
status: draft | approved | stale
updated: YYYY-MM-DD
---
```

Keep approval evidence in prose near the status or in version control; do not create a separate workflow database.

Use `draft | approved` for requirements, `draft | approved | stale` for proposals and designs, and `passed | partial | failed | stale` for verification reports. `stale` means an upstream material change invalidated the artifact; it is never an approval state.

## Control Drift

Treat approved requirements as the source of scope. A proposal chooses an approach, a design explains how to build it, implementation realizes the design, and verification proves the acceptance criteria. A downstream artifact must not quietly introduce a new requirement.

When a material change appears:

1. Stop at the current phase and identify whether the change affects scope, approach, design, or only local implementation detail.
2. Update the earliest affected artifact. Return it to `draft` and obtain explicit approval.
3. Mark every affected downstream artifact `stale`; do not treat its previous approval or test result as current evidence.
4. Revise downstream artifacts in order, preserving unaffected content, and repeat the required approvals and verification.

A material change alters a goal, non-goal, acceptance criterion, chosen approach, public behavior, interface, owned data, security rule, migration, or operational requirement. Renaming a local variable or choosing an equivalent library call is normally not material.

Before advancing phases, perform a short alignment check:

- every requirement and goal is addressed by the proposal;
- every proposed responsibility is realized by the design;
- every material code change is authorized by the approved design;
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

### Implementation

Read the approved requirements, proposal, and design before editing code. Inspect the current implementation and reuse repository conventions. Implement the smallest complete change that satisfies the acceptance criteria. Add or update executable tests in the repository's normal locations and keep documentation synchronized with material discoveries.

Do not mark delivery verified merely because implementation is complete. If implementation requires a material deviation, follow the drift-control procedure before continuing.

### Testing And Verification

Read [references/testing.md](references/testing.md). Create `testing/plan.md` when verification begins, run the relevant checks, and write `testing/report.md` from actual evidence. Map every acceptance criterion to a test, inspection, or explicitly unverified item.

### Alignment Audit

At any phase, the user may ask for an alignment or drift check. Compare the approved requirements, proposal, design, current implementation, executable tests, and verification report in that order. Report missing coverage, unauthorized behavior, contradictions, stale artifacts, and tests that no longer prove an acceptance criterion. Do not explain away a mismatch by editing the upstream intent after the fact; apply the change-control procedure if the user chooses to accept it.

### Core Change History

Read [references/core-history.md](references/core-history.md) when the user asks to track important classes or components across Git commits. After initialization, use the target project's `.agent/scripts/generate_core_history.py` to regenerate the Markdown projection from Git; the copy in this skill package is only the initializer's source. Git remains the authority, and the Markdown is derived and may be regenerated after amend, rebase, merge, or rollback. Do not auto-commit generated output from a Git hook.

## Completion

A work item is complete only when:

- the approved requirements, proposal, and design reflect the delivered behavior;
- implementation and executable tests are present in their normal repository locations;
- `testing/report.md` records the commands and checks actually performed;
- every acceptance criterion is passed or clearly reported as failed or unverified; and
- remaining limitations and follow-up work are explicit; and
- no artifact used as evidence is marked `draft` or `stale`.

At completion, check whether the work established or invalidated durable cross-task knowledge. Update `.agent/memory.md` only when it did; do not create a memory entry merely to summarize the completed task.

Create or update a note under `.agent/notes/` only when the work establishes a cross-feature decision whose rationale should guide future changes. Do not duplicate an ordinary proposal or design there.
