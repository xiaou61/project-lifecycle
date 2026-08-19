#!/usr/bin/env python3
"""在目标项目中初始化 .agent 生命周期工作区。"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


WORKSPACE_DIRS = (
    "project",
    "features",
    "references",
    "notes",
    "history",
    "scripts",
)

WORKSPACE_README = """# .agent 项目工作区

本目录保存由已安装的 `project-lifecycle` skill 管理的项目过程资料，不保存 Skill 本体。Skill 本体由 Codex 从本地 Skill 安装目录加载。

```text
.agent/
  memory.md                当前有效、可快速检索的项目长期记忆
  project/                 整体项目的需求、提案、设计和验证资料
  features/<功能>/         单个功能的需求、提案、设计和验证资料
  references/              多个工作项共享的项目参考资料
  notes/                   跨功能、长期有效的决策理由
  history/                 根据 Git 生成的核心组件历史
  scripts/                 项目内使用的确定性辅助脚本
```

项目源代码和可执行测试仍放在项目原有目录。`testing/` 只保存测试计划和验证报告。

生命周期状态使用机器可读的英文值：`draft`、`approved`、`stale`、`passed`、`partial`、`failed`。
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
        return "保留"
    path.write_text(content, encoding="utf-8", newline="\n")
    return "创建"


def copy_if_missing(source: Path, destination: Path) -> str:
    if destination.exists():
        return "保留"
    shutil.copyfile(source, destination)
    return "创建"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="目标项目根目录，默认当前目录")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.exists() or not target.is_dir():
        print(f"初始化失败：目标不是现有目录：{target}", file=sys.stderr)
        return 2

    workspace = target / ".agent"
    workspace.mkdir(exist_ok=True)
    for relative in WORKSPACE_DIRS:
        (workspace / relative).mkdir(exist_ok=True)

    readme_status = create_text_if_missing(workspace / "README.md", WORKSPACE_README)
    memory_status = create_text_if_missing(workspace / "memory.md", MEMORY_TEMPLATE)
    generator_status = copy_if_missing(
        Path(__file__).with_name("generate_core_history.py"),
        workspace / "scripts" / "generate_core_history.py",
    )

    print(f".agent 初始化完成：{workspace}")
    print(f"{readme_status}：{workspace / 'README.md'}")
    print(f"{memory_status}：{workspace / 'memory.md'}")
    print(f"{generator_status}：{workspace / 'scripts' / 'generate_core_history.py'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
