# Core Component Change History

Use this mode when a project needs a readable timeline for important classes or components.

## Source Of Truth

Git owns commit identity, author, timestamps, messages, renames, and changed paths. The generated Markdown is a deterministic projection of that history. Never edit the generated report by hand and never treat it as a replacement for `git log`.

The generator cannot reliably infer architectural importance or a language-independent class boundary from commit text. Declare the tracked units in a small project config:

```json
{
  "units": [
    {
      "id": "user-service",
      "name": "UserService",
      "paths": ["src/services/user-service.ts"]
    }
  ]
}
```

Use stable `id` values. `paths` are repository-relative and may contain more than one file. Include the current path after a rename and retain an old path when its history should remain part of the same unit. A unit is file-scoped: if a file contains several classes and they need separate histories, declare separate paths or keep a manual symbol note beside the generated report. Do not claim symbol-level precision that Git path history does not provide.

Recommended locations are:

```text
.agent/core-components.json
.agent/history/core-components.md
```

For a work-item-specific history, use the same pair below that change's artifact root instead.

## Generated Entry

Each unit entry should show:

- the configured unit name and tracked paths;
- commit date and author;
- abbreviated commit hash;
- commit subject;
- changed paths reported by Git.

This answers when, by whom, and where the repository changed the unit. The report does not invent a reason or impact statement. Record those in the commit body, the approved design, or an Agent Note when the decision is cross-feature and durable.

## Update Modes

The normal command is:

```sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

For CI or a review check, add `--check`; it exits non-zero when the report is absent or does not match current Git history. The output is deterministic and contains no generation timestamp.

If the project wants an update after every commit, install an explicit `post-commit` hook that runs the command. Adapt the paths to the repository; the hook is project policy, not a hidden side effect of this skill:

```sh
#!/bin/sh
python .agent/scripts/generate_core_history.py \
  --config .agent/core-components.json \
  --output .agent/history/core-components.md
```

The hook may update a tracked report in the working tree, but it must not create a second commit automatically. This avoids recursive commits, hides no generated diff, and leaves the user in control of whether the projection belongs in the next commit. A repository-wide hook manager may version this hook separately.

Do not run a model or call an external service from the hook to summarize a commit. That makes history nondeterministic and can expose source or credentials. If a human-readable explanation is needed, ask for it during the lifecycle workflow and store it in the relevant proposal, design, or note.

## Drift And Renames

Regenerate rather than append. Rewriting history, squashing, amending, and reverting can invalidate an append-only Markdown log. The script uses Git path history with rename following where Git supports it and deduplicates commits when a unit tracks multiple paths. After a rename, update `paths` before the next generation so post-rename commits are included; document a renamed or split class in an Agent Note when its identity changed, and do not silently merge unrelated histories.
