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
    "html",
    "history",
    "scripts",
)

LEGACY_WORKSPACE_DIRS = (
    "project",
    "features",
)

WORKSPACE_README = """# .agent 项目工作区

本目录保存已安装 `project-lifecycle` Skill 使用的项目资料，不保存 Skill 本体。根目录 `AGENTS.md` 负责入口路由；若存在 `AGENTS.override.md`，按更高优先级使用。

```text
.agent/
  INDEX.md                  按模块定位代码、规格、变更和理解材料
  memory.md                 跨任务仍有效的长期记忆
  rules/always.md           用户确认后的项目常驻规范
  specs/                    多个工作项共享的当前事实
  changes/WORK-编号-中文名/  受管理需求的生命周期工件
  notes/ references/        决策理由与共享资料
  html/                     用户同意后生成的项目理解型 HTML
  history/                  更新历史与 Git 历史视图
  scripts/                  项目内确定性辅助脚本（不放 Skill 状态脚本）
```

`specs/` 保存当前共享事实，`changes/` 保存一次变更的依据、任务和验证；`history/updates.md` 追加每轮变更、决策、依据、验证和本地提交边界，`history/core-components.md` 是 Git 历史的生成视图；源代码与可执行测试仍在项目原有目录。`always.md` 只保存经用户确认且适用于多个任务的长期规则，单次约束写在对应 `requirements.md`。`html/` 只在用户明确同意后写入理解材料，空目录本身不表示已批准。

Git 工作区有未提交改动时，可在对应工作项下增加 `workspace.md`，记录基准 commit、每条改动路径的归属和说明，供恢复探针核对。

直接用自然语言开始、确认、继续或查询状态即可。`WORK-*` 只用于跨对话定位，不代表阶段批准；恢复顺序、门槛、澄清、验证和完成语义统一见已安装 Skill 的 `references/workflow.md`。
"""

INDEX_TEMPLATE = """---
artifact: project_index
status: active
---

# 项目总索引

本页只负责按模块导航，帮助定位“代码改在哪里、依据和验证到哪里看”。工作项阶段、批准、任务进度和验证结果仍以对应工件及 `project-lifecycle.ps1 status` 输出为准，不在这里重复维护。状态、恢复和严格校验脚本属于已安装 Skill 的内部实现，不在目标项目 `.agent/scripts/` 中查找。

## 内容在哪里

| 内容 | 位置 |
| --- | --- |
| 项目常驻规范 | `.agent/rules/always.md` |
| 当前稳定规格 | `.agent/specs/` |
| 需求与变更依据 | `.agent/changes/WORK-编号-中文名/` |
| 决策说明与共享资料 | `.agent/notes/`、`.agent/references/` |
| 长期记忆 | `.agent/memory.md` |
| 项目理解型 HTML | `.agent/html/` |
| 更新历史与 Git 历史视图 | `.agent/history/updates.md`、`.agent/history/core-components.md` |

## 模块索引

只登记已经从仓库确认的模块和路径；发现新模块或路径发生实质变化时更新对应行。

| 模块 | 源码或配置 | 测试 | 稳定规格 | 相关工作项 |
| --- | --- | --- | --- | --- |

当前尚未登记项目模块。

## HTML 理解材料

将用于解释架构、流程、状态机、数据流或交互的独立 HTML 放在 `.agent/html/`，但必须先取得用户明确同意。初始化器只创建空目录；新增保留文件后，在这里补充名称、用途和相对路径；这类材料不替代源码、测试或批准工件。

当前暂无 HTML 理解材料。

## 查看一次变更

| 想确认什么 | 查看位置 |
| --- | --- |
| 为什么要改、验收什么 | 对应工作项的 `requirements.md` |
| 为什么选择这种方案 | `proposal.md`、`design.md` |
| 实际改哪些步骤 | `tasks.md` |
| 当前未提交文件属于谁 | `workspace.md` 与 `git diff` |
| 如何证明改对 | `testing/plan.md`、`testing/report.md` |
| 交付后项目应保持什么行为 | `.agent/specs/` |
"""

UPDATE_HISTORY_TEMPLATE = """---
artifact: update-history
status: active
schema_version: 1
---

# 项目更新历史

这里按时间顺序追加每轮实际变更、关键决策、依据、验证结果和 Git 边界。它是面向人阅读的项目时间线，不替代 `.agent/changes/` 工件或 Git 历史。

记录格式见已安装 Skill 的 `references/update-history.md`。每条记录至少包含变更、决策、依据、验证、本地提交和远端推送字段；没有实际持久化改动的聊天不追加；不要删除或覆盖旧记录。

## 记录

当前暂无更新记录。
"""

AGENTS_TEMPLATE = """# 项目协作说明

本项目使用已安装的 `project-lifecycle` Skill 管理需要持久追踪、多人协作或有明显风险的工作。

## 入口规则

- 低风险、边界清楚的单文件改动：确认目标 -> 修改 -> 窄验证，不创建 `WORK-*`。
- 重要工作开始或恢复时，先读取适用入口规则、`.agent/rules/always.md`、状态结果和当前工件；多仓库先从外层 `PROJECT-INDEX.md` 定位真实项目。
- 需要定位模块、历史变更或理解材料时先读 `.agent/INDEX.md`；它只做导航，不替代状态检查。
- 只有受管理需求创建 `WORK-*`；阶段批准、澄清、漂移、验证和完成语义统一遵循 Skill 的 `references/workflow.md`。
- 未完成硬依赖阻断实现和验收；重大范围、接口、数据、安全、部署或架构变化回到最早受影响工件。
- 规则未确认前不得进行实现、部署、迁移或数据变更；验证结果必须据实记录。
- 每次实际修改后追加 `.agent/history/updates.md`，记录变更、决策、依据、验证和本地提交边界；远端 `push` 必须得到用户明确授权。

若未发现 `$project-lifecycle`，请先说明 Skill 未安装。
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
                workspace / "INDEX.md",
                workspace / "memory.md",
                workspace / "rules" / "always.md",
                workspace / "history" / "updates.md",
                workspace / "scripts" / "generate_core_history.py",
            ),
            "文件",
        )

        workspace.mkdir(exist_ok=True)
        for relative in WORKSPACE_DIRS:
            (workspace / relative).mkdir(exist_ok=True)

        agents_status = create_text_if_missing(agents_path, AGENTS_TEMPLATE)
        readme_status = create_text_if_missing(workspace / "README.md", WORKSPACE_README)
        index_status = create_text_if_missing(workspace / "INDEX.md", INDEX_TEMPLATE)
        memory_status = create_text_if_missing(workspace / "memory.md", MEMORY_TEMPLATE)
        history_status = create_text_if_missing(
            workspace / "history" / "updates.md", UPDATE_HISTORY_TEMPLATE
        )
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
    print(f"{index_status}：{workspace / 'INDEX.md'}")
    print(f"{memory_status}：{workspace / 'memory.md'}")
    print(f"{history_status}：{workspace / 'history' / 'updates.md'}")
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
