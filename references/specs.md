# Stable Project Specs

Use this reference when the project needs a durable statement of current behavior, shared contracts, architecture boundaries, domain rules, or operational invariants. Stable specs are the project's small, human-readable current-state view; they are not a second source-code tree and they are not a list of every feature ever discussed.

## Two Folders, Two Questions

```text
.agent/specs/                  What should be true today?
.agent/changes/<work-slug>/    What are we changing, and how will we prove it?
```

Use one file per meaningful domain or contract, for example:

```text
.agent/specs/
  architecture.md
  auth.md
  billing.md
  operations.md
```

Do not create a file merely because a folder exists. For a small project, one `project.md` or no stable spec at all may be enough. Keep executable behavior in source and tests; a spec should state the contract and point to authoritative code, tests, or references when useful.

## What Belongs In A Spec

Record facts that several future work items need, such as:

- externally observable behavior and scenarios;
- public interfaces and compatibility rules;
- ownership and boundaries between components;
- data invariants, security constraints, or migration rules; and
- operational expectations that are part of the product contract.

Do not put temporary brainstorming, an unapproved proposal, task checkboxes, chat transcripts, generated Git history, credentials, or unsupported guesses in `specs/`.

## Change And Reconciliation

1. Read the affected stable spec before drafting a change.
2. In `.agent/changes/<work-slug>/requirements.md`, describe the requested outcome and acceptance criteria. State whether a stable spec is expected to change.
3. After approval, record the approach in `proposal.md`, implementation detail in `design.md`, and execution order in `tasks.md`.
4. Implement and verify against the approved artifacts.
5. If the delivered behavior changes a stable contract, update the affected spec from the verified result. Preserve the change documents as the rationale and evidence.
6. Optionally move the completed change directory to `.agent/changes/archive/YYYY-MM-DD-<work-slug>/`. Archive only after verification; keep the files intact so Git can show the complete decision trail.

Do not update a stable spec before implementation just to make a failing or unauthorized change look compliant. If implementation reveals that the spec or approved requirements were wrong, stop, return the earliest affected artifact to `draft`, and obtain approval.

## Authority And Conflicts

- Approved requirements define the scope of the current change.
- Approved design and tasks define the authorized implementation path.
- Stable specs define the intended current contract across changes.
- Source code and executable tests show what is actually implemented.
- Git history shows when the artifacts and code changed.

A conflict is useful evidence of drift. Report it and identify which artifact must be revised; do not silently choose the document that makes the current code look correct.
