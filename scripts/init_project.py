#!/usr/bin/env python3
"""在目标项目中初始化 .agent 生命周期工作区和项目级 AGENTS.md。"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


WORKSPACE_DIRS = (
    "specs",
    "changes",
    "references",
    "notes",
    "history",
    "scripts",
)

LEGACY_WORKSPACE_DIRS = (
    "project",
    "features",
)

WORKSPACE_README = """# .agent 项目工作区

本目录保存由已安装的 `project-lifecycle` skill 管理的项目过程资料，不保存 Skill 本体。Skill 本体由 Codex 从本地 Skill 安装目录加载。

项目根目录的 `AGENTS.md` 是 Codex 的项目级入口规则；它负责说明何时使用 Skill，本目录负责保存具体项目资料。若存在 `AGENTS.override.md`，Codex 会优先采用它。

```text
.agent/
  memory.md                当前有效、可快速检索的项目长期记忆
  specs/                   项目当前仍有效的共享规格与契约
  changes/<工作项>/        每个项目或功能变更的完整生命周期资料
  references/              多个工作项共享的项目参考资料
  notes/                   跨功能、长期有效的决策理由
  history/                 根据 Git 生成的核心组件历史
  scripts/                 项目内使用的确定性辅助脚本
```

`specs/` 只保存多个工作项共享的当前事实；项目初始化、功能、重构和迁移都使用 `changes/<工作项>/`，只调整文档详细程度，不再使用不同的目录体系。

每个受管理工作项按需包含 `requirements.md`、`proposal.md`、`design.md`、`tasks.md` 和 `testing/`。项目源代码和可执行测试仍放在项目原有目录；`testing/` 只保存测试计划和验证报告。

生命周期状态使用机器可读的英文值：`draft`、`approved`、`stale`、`passed`、`partial`、`failed`。
"""

AGENTS_TEMPLATE = """# 项目协作说明

本项目使用已安装的 `project-lifecycle` Skill 管理重要开发工作。

## 工作规则

- 重要功能、跨模块修改或项目级开发，优先使用 `$project-lifecycle`。
- 首次使用前检查项目根目录的 `.agent/`；不存在时运行该 Skill 的初始化器。
- 初始化只在缺失时创建项目级 `AGENTS.md`，并创建或补充 `.agent/`；不会覆盖已有资料。
- 源代码和可执行测试仍放在项目原有目录，`.agent/changes/<工作项>/` 保存需求、提案、设计、任务和验证资料。
- 开始重要任务前读取 `.agent/memory.md`、相关 `.agent/specs/` 和生命周期文档。
- 需求、提案、设计、任务和验证按审批门槛推进；Agent 不自行批准。
- 发现实质性范围、接口、数据、安全或架构变化时，停止并按漂移控制流程更新上游文档。
- 完成任务后，仅在产生跨任务长期知识时更新 `.agent/memory.md`。
- 孤立的小改动不强制创建完整生命周期文档。

如果当前环境没有发现 `$project-lifecycle`，请先说明 Skill 未安装，不要假装已经加载它。
"""

MEMORY_TEMPLATE = """# 项目长期记忆

本文件只记录会影响后续多个任务、并且当前仍有使用价值的项目知识。它不是聊天记录、任务日志或待办清单。

- 使用 `rg -n "^## MEM-" .agent/memory.md` 列出全部记忆。
- 使用 `rg -n -i -C 6 "关键词|标签" .agent/memory.md` 查找相关记忆。
- `active` 表示当前有效，`stale` 表示需要复核，`superseded` 表示已有替代条目。
- 详细决策理由放入 `.agent/notes/`，共享资料放入 `.agent/references/`。

## 记忆条目

当前暂无长期记忆。
"""


def create_text_if_missing(path: Path, content: str) -> str:
    if path.exists():
        if not path.is_file():
            raise RuntimeError(f"目标路径已存在但不是文件：{path}")
        return "保留"
    path.write_text(content, encoding="utf-8", newline="\n")
    return "创建"


def copy_if_missing(source: Path, destination: Path) -> str:
    if destination.exists():
        if not destination.is_file():
            raise RuntimeError(f"目标路径已存在但不是文件：{destination}")
        return "保留"
    shutil.copyfile(source, destination)
    return "创建"


def validate_existing_paths(paths: tuple[Path, ...], expected: str) -> None:
    for path in paths:
        if path.exists() and (not path.is_dir() if expected == "目录" else not path.is_file()):
            raise RuntimeError(f"目标路径已存在但不是{expected}：{path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="目标项目根目录，默认当前目录")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.exists() or not target.is_dir():
        print(f"初始化失败：目标不是现有目录：{target}", file=sys.stderr)
        return 2

    agents_path = target / "AGENTS.md"
    agents_existed = agents_path.exists()
    workspace = target / ".agent"
    try:
        validate_existing_paths((agents_path,), "文件")
        validate_existing_paths((workspace, *(workspace / relative for relative in WORKSPACE_DIRS)), "目录")
        validate_existing_paths(
            (
                workspace / "README.md",
                workspace / "memory.md",
                workspace / "scripts" / "generate_core_history.py",
            ),
            "文件",
        )

        workspace.mkdir(exist_ok=True)
        for relative in WORKSPACE_DIRS:
            (workspace / relative).mkdir(exist_ok=True)

        agents_status = create_text_if_missing(agents_path, AGENTS_TEMPLATE)
        readme_status = create_text_if_missing(workspace / "README.md", WORKSPACE_README)
        memory_status = create_text_if_missing(workspace / "memory.md", MEMORY_TEMPLATE)
        generator_status = copy_if_missing(
            Path(__file__).with_name("generate_core_history.py"),
            workspace / "scripts" / "generate_core_history.py",
        )
    except (OSError, RuntimeError) as error:
        print(f"初始化失败：{error}", file=sys.stderr)
        return 2

    print(f".agent 初始化完成：{workspace}")
    print(f"{agents_status}：{agents_path}")
    print(f"{readme_status}：{workspace / 'README.md'}")
    print(f"{memory_status}：{workspace / 'memory.md'}")
    print(f"{generator_status}：{workspace / 'scripts' / 'generate_core_history.py'}")
    if agents_existed:
        print("提示：未修改已有 AGENTS.md；请确认其中包含何时使用 $project-lifecycle 的项目规则。")
    if (target / "AGENTS.override.md").is_file():
        print("提示：检测到 AGENTS.override.md；Codex 会优先采用它，AGENTS.md 作为基础规则暂不生效。")
    legacy = [workspace / relative for relative in LEGACY_WORKSPACE_DIRS if (workspace / relative).exists()]
    if legacy:
        print("提示：检测到旧版工作目录，已原样保留，不会自动移动资料：")
        for path in legacy:
            print(f"- {path}")
        print("迁移建议：.agent/project/ -> .agent/changes/project-foundation/；.agent/features/<名称>/ -> .agent/changes/<名称>/。")
        print("迁移完成后，请同步更新 AGENTS.md 和 .agent/README.md 中的旧路径；初始化器不会覆盖这两个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
