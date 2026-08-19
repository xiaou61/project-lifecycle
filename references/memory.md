# Project Memory

Use this reference when reading or maintaining the target project's `.agent/memory.md`.

## Purpose And Authority

Project memory is a compact retrieval layer for durable knowledge that may affect future tasks. It answers "what should the next agent remember?" It does not replace:

- approved requirements, proposals, or designs;
- current source code and executable tests;
- Git history;
- `.agent/notes/`, which explains why a durable decision was made; or
- `.agent/references/`, which holds shared source material and external facts.

When memory conflicts with a current authoritative source, follow and cite the authoritative source, then mark the memory `stale` or replace it. A memory entry never approves a lifecycle gate or expands scope.

## Retrieve Before Work

For a substantial task, first list entry headings:

```sh
rg -n "^## MEM-" .agent/memory.md
```

Then search using a small set of terms from the feature name, module, affected paths, constraints, and technologies:

```sh
rg -n -i -C 6 "auth|session|security" .agent/memory.md
```

Read matching entries and their cited sources when the decision is material. Read the whole file only when it is small or the task is repository-wide. If `rg` is unavailable, use the environment's ordinary text search or read the file directly.

## What To Record

Record an item only when it is evidence-backed and likely to affect work beyond the current task, such as:

- a stable architectural boundary or invariant;
- a cross-feature convention or constraint;
- an explicitly confirmed, durable user or team preference;
- a non-obvious operational procedure that will be reused; or
- a verified failure lesson with a concrete prevention rule.

Do not record task progress, ordinary implementation details, chat summaries, TODO items, temporary errors, unsupported guesses, secrets, credentials, personal data, or content already easy to discover from the repository. Link to a detailed note or reference instead of copying it.

## Entry Format

Store entries under `## 记忆条目` using this compact schema:

```markdown
## MEM-001 | active | constraint

- 摘要：所有公开 API 的时间字段统一使用 UTC ISO 8601。
- 标签：`api` `time` `serialization`
- 范围：`src/api/`
- 依据：`.agent/notes/api-time-format.md`
- 记录：2026-08-19
- 复核：2026-08-19
- 失效条件：公开 API 版本策略发生变化。
```

Use these rules:

- IDs use `MEM-001`, `MEM-002`, and so on. Allocate the next unused number; never renumber or reuse an ID.
- Status is `active`, `stale`, or `superseded`.
- Category is normally `constraint`, `architecture`, `convention`, `preference`, `operation`, or `lesson`. Add a category only when none of these describes a recurring real need.
- Tags use short lowercase terms already used in the repository when possible.
- Scope names the project area, feature, module, path, interface, or requirement to which the entry applies.
- Evidence cites an approved artifact, note, reference, test, commit, repository path, or dated explicit user confirmation.
- Review is the last date the evidence was checked, not merely the date the text was edited.
- Add an invalidation condition only when one can be stated concretely.
- Keep the summary independently useful. Add detail below the fields only when it changes how the memory should be applied.

Remove `当前暂无长期记忆。` when adding the first entry.

## Maintain Without Accumulating Noise

- Search for an existing entry before adding one. Update it when the fact is the same; do not append a paraphrased duplicate.
- Mark an entry `stale` when its evidence may no longer be current and re-check it before relying on it.
- When a conclusion is replaced, create the new entry, mark the old one `superseded`, and add `- 替代：MEM-xxx` to the old entry.
- Keep active entries concise. Move detailed rationale to `.agent/notes/` and source material to `.agent/references/`.
- Preserve useful change history through Git. The working memory should optimize current retrieval, not retain every obsolete explanation inline.

At the end of a phase or substantial task, review whether durable knowledge was added, changed, or invalidated. Update memory only when the answer is yes, and tell the user which IDs changed.
