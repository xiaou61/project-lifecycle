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
    "rules",
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

本目录保存项目的长期规则、稳定规格、工作项资料和验证证据；Skill 本体由 Codex 从安装目录加载。

项目根目录的 `AGENTS.md` 是入口规则；若存在 `AGENTS.override.md`，Codex 会优先采用它。

```text
.agent/
  memory.md                当前有效、可快速检索的项目长期记忆
  rules/always.md          用户确认后生效的项目常驻规范（初始化时不自动创建）
  specs/                   项目当前仍有效的共享规格与契约
  changes/WORK-001-中文名/ 每个需求或变更的完整生命周期资料
  references/              多个工作项共享的项目参考资料
  notes/                   跨功能、长期有效的决策理由
  history/                 根据 Git 生成的核心组件历史
  scripts/                 项目内使用的确定性辅助脚本
```

低风险小修复可以不创建工作项。需要跨会话追踪的普通功能可在 `requirements.md` 使用 `workflow: compact`；高风险工作再按需求、方案、设计、任务和验证逐步记录。

`rules/always.md` 只保存经用户确认、且适用于项目多个任务的长期规范。初始化器不会替项目猜测规则；单次约束写在对应 `requirements.md`。

项目源代码和可执行测试仍放在项目原有目录；`testing/` 只保存测试计划和验证报告。

生命周期状态使用机器可读的英文值：`draft`、`approved`、`stale`、`passed`、`partial`、`failed`。

直接用自然语言开始、确认、继续或查询状态。用户点名 `WORK-*` 时，Skill 从入口规则、状态和当前工件恢复，不依赖聊天记忆；“继续”只推进已获授权的动作。需要时用“当前 / 本次 / 下一步”说明方向，跨会话再给出接力。

跨对话接力：新对话可说“$project-lifecycle 继续实施 WORK-003”，Skill 会重新读取规则、状态和当前工件。

详细恢复、阶段和关系协议由已安装 Skill 的 `references/workflow.md` 提供。不要创建 `current.md` 或 `state.json`。
"""

AGENTS_TEMPLATE = """# 项目协作说明

本项目使用已安装的 `project-lifecycle` Skill 管理需要持久追踪的开发工作。

## 工作规则

- 低风险、边界清楚的小修复可直接修改并验证，不必创建 `WORK-*`。
- 重要工作开始或恢复时使用 `$project-lifecycle`，读取项目规则、工作项状态和当前工件后再行动。
- 实质性范围、接口、数据、安全或架构变化时停止并重新确认，不静默扩大目标。
- 测试未运行、失败或存在人工缺口时据实报告，不把文档状态当成测试事实。
- 不创建 `.agent/current.md` 或 `state.json`；源代码和可执行测试保留在项目原有目录。
- 需要跨会话追踪时创建 `WORK-*`，并按当前风险保留必要工件。
- 自然语言、用户点名 `WORK-*` 或“继续”都可作为入口；状态需要时用“当前 / 本次 / 下一步”说明，跨会话时再给出接力。

详细阶段协议由已安装 Skill 的 `references/workflow.md` 提供。若未发现 `$project-lifecycle`，请先说明 Skill 未安装。
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
                workspace / "rules" / "always.md",
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
    rules_path = workspace / "rules" / "always.md"
    if rules_path.is_file():
        print(f"保留：{rules_path}")
    else:
        print(f"待用户确认后创建：{rules_path}")
        print("提示：初始化不会写入固定项目规则；请先检查项目并向用户提出规则草案，确认后再创建 always.md。")
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
        print("迁移建议：先扫描现有和归档工作项分配后续 WORK 编号，再迁移到 .agent/changes/WORK-编号-中文名/。")
        print("迁移完成后，请同步更新 AGENTS.md 和 .agent/README.md 中的旧路径；初始化器不会覆盖这两个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
