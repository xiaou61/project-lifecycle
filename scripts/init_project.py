#!/usr/bin/env python3
"""在目标项目中初始化 .agent 生命周期工作区和项目级 AGENTS.md。"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
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

本目录保存由已安装的 `project-lifecycle` skill 管理的项目过程资料，不保存 Skill 本体。Skill 本体由 Codex 从本地 Skill 安装目录加载。

项目根目录的 `AGENTS.md` 是 Codex 的项目级入口规则；它负责说明何时使用 Skill，本目录负责保存具体项目资料。若存在 `AGENTS.override.md`，Codex 会优先采用它。

```text
.agent/
  memory.md                当前有效、可快速检索的项目长期记忆
  rules/always.md          当前项目所有任务都适用的常驻规范
  specs/                   项目当前仍有效的共享规格与契约
  changes/WORK-001-中文名/ 每个需求或变更的完整生命周期资料
  references/              多个工作项共享的项目参考资料
  notes/                   跨功能、长期有效的决策理由
  history/                 根据 Git 生成的核心组件历史
  scripts/                 项目内使用的确定性辅助脚本
```

`specs/` 只保存多个工作项共享的当前事实；项目初始化、功能、重构和迁移都使用 `changes/WORK-编号-中文名/`，只调整文档详细程度，不再使用不同的目录体系。

`rules/always.md` 只保存这个项目每个任务都适用的长期规范。初始化器提供最小安全模板，不猜测项目的测试命令、目录或技术栈；维护者应在开始重要开发前补全“待项目确认”的项目事实。单次需求的特殊约束写在对应 `requirements.md`，不要把临时取舍提升为常驻规范。

每个受管理工作项按需包含 `requirements.md`、`proposal.md`、`design.md`、`tasks.md` 和 `testing/`。项目源代码和可执行测试仍放在项目原有目录；`testing/` 只保存测试计划和验证报告。

生命周期状态使用机器可读的英文值：`draft`、`approved`、`stale`、`passed`、`partial`、`failed`。

## 日常使用

直接用自然语言开始或继续工作即可，例如：“我想增加用户登录”“这版需求确认，继续给方案”“方案可以，做设计”“按计划开始做”“测试一下”“当前任务状态”“所有需求有哪些阻塞”。不需要记忆目录或阶段命令。

每个受管理需求都有稳定 `WORK-*` 编号和中文名称，例如 `WORK-003 · 用户登录`；名称贯穿需求、设计、开发和测试。Skill 会从现有工件推导阶段、实施任务计数、依赖、关联和下一步，并用“当前 / 本次 / 下一步”简短说明方向。`继续` 只推进已经获得授权的动作，不等于批准当前需求、方案、设计或任务计划。

## 跨对话接力

`WORK-*` 是跨对话定位键，不是直接写代码的命令，也不代表阶段批准。新对话已经打开本项目时，可以直接说：

```text
$project-lifecycle 继续实施 WORK-003。先恢复规范和状态；满足实施门槛就按已批准任务计划执行，否则告诉我还缺什么确认。
```

Agent 会重新读取项目入口规则、`rules/always.md`、状态查询结果和该工作项的当前阶段工件。任务计划已批准、项目事实已配置、硬依赖已完成且没有漂移时，直接继续开发；否则停在最早缺失阶段，不要求你重讲整条需求。每次实质性推进后，状态块末尾会给出下一次可直接使用的“接力”提示词。

```text
需求出现 -> 讨论收敛 -> 设计决策（方案 -> 详细设计 -> 实施计划） -> 开发实现 -> 测试验收 -> 完成沉淀
```

硬依赖使用 `depends_on`，软关联使用 `related_to`。不要另外维护 `current.md` 或 `state.json`；工作项身份、关系、工件状态、任务状态和验证报告就是查询依据。

跨对话的完整执行协议（包括 `WORK-*` 如何恢复、何时允许实施、标准状态块和接力提示词）由已安装 Skill 的 `references/workflow.md` 统一维护。需要恢复或接力时使用 `$project-lifecycle`，不要在项目里复制另一份流程。
"""

AGENTS_TEMPLATE = """# 项目协作说明

本项目使用已安装的 `project-lifecycle` Skill 管理重要开发工作。

## 工作规则

- 重要功能、跨模块修改或项目级开发，优先使用 `$project-lifecycle`。
- 首次使用前检查项目根目录的 `.agent/`；不存在时运行该 Skill 的初始化器。
- 初始化只在缺失时创建项目级 `AGENTS.md`，并创建或补充 `.agent/`；不会覆盖已有资料。
- 源代码和可执行测试仍放在项目原有目录，`.agent/changes/WORK-编号-中文名/` 保存需求、提案、设计、任务和验证资料。
- 开始重要任务前读取 `.agent/memory.md`、相关 `.agent/specs/` 和生命周期文档。
- 开始或恢复任何受管理任务前读取 `.agent/rules/always.md`；上下文压缩后按入口规则、项目规范、状态查询、工作项需求和当前阶段工件重新加载。
- 开始或恢复受管理工作时，先让 Skill 从现有工件判断当前工作项、阶段和下一步；不要按文件时间戳猜测。
- 用户点名 `WORK-*` 时视为恢复该工作项的请求，必须使用 `$project-lifecycle` 重新加载规范和工件；编号用于定位，不等于批准或允许直接改代码。
- 跨对话恢复、阶段门槛和接力提示词以 Skill 的 `references/workflow.md` 为唯一协议来源；不要在项目里另建 `current.md`、`state.json` 或复制流程。
- 用户可以直接说需求、确认决定、询问状态或说“继续”，不要求使用固定阶段命令。
- 每个新需求由 Agent 主动给出简短中文名称并分配不复用的 `WORK-*` 编号；同一名称贯穿全部阶段。
- “当前任务状态”默认返回当前工作项阶段、内部任务计数、关系、阻塞和下一步；点名 `WORK-*`、中文名称或 `TASK-*` 时查询对应项。
- 跨需求只使用 `depends_on` 硬依赖和 `related_to` 软关联；实现前阻断未完成硬依赖，软关联跨阶段前做影响检查。
- 每次实质性推进后，用“当前 / 本次 / 下一步 / 接力”简短汇报；已有 `WORK-*` 时，接力行给出可直接用于新对话的恢复提示词。
- 阶段状态只用于定位；跨阶段前还要比较需求、方案、设计、任务、代码和测试的实际内容。
- 需求、提案、设计、任务和验证按审批门槛推进；Agent 不自行批准。
- “继续”不是批准；“这版需求确认”“方案可以”“设计没问题”“按任务计划做”等上下文明确的自然语言可以构成批准。
- 发现实质性范围、接口、数据、安全或架构变化时，停止并按漂移控制流程更新上游文档。
- 完成任务后，仅在产生跨任务长期知识时更新 `.agent/memory.md`。
- 孤立的小改动不强制创建完整生命周期文档。
- 不创建 `.agent/current.md`、`state.json` 或手工索引来重复生命周期状态。
- 项目规范使用 `MUST / SHOULD / MAY`；工作项可以收紧项目规范，不能静默放宽；例外必须记录范围、理由、批准人和验证方式。

如果当前环境没有发现 `$project-lifecycle`，请先说明 Skill 未安装，不要假装已经加载它。
"""

RULES_TEMPLATE = """---
artifact: project_rules
scope: project
status: active
configured: false
version: 1
updated: {{UPDATED_DATE}}
---

# 项目常驻规范

本文件适用于当前项目的每一个受管理任务。它不是某个功能的需求、方案或任务清单；只记录多个未来任务仍然成立的项目事实。上下文压缩、换会话或用户说“继续”时，Agent 必须重新读取本文件。

## 规范级别（MUST / SHOULD / MAY）

- `MUST`：硬约束，不得跳过。需要例外时先记录并取得明确批准。
- `SHOULD`：默认做法，有充分理由才偏离，并在当前工作项中说明。
- `MAY`：可选建议，不构成完成门槛。

## MUST：所有任务都要遵守

- 使用项目已经确认的技术栈、包管理器和源码/测试目录；未知内容先检查，不凭空假设。
- 不把密钥、个人数据或生产数据写入代码、日志、测试样例和 `.agent/`。
- 任何行为、接口、数据、安全或迁移变化，都必须在当前工作项的需求和验收标准中有依据。
- 代码变更后运行与影响范围匹配的真实检查；没有运行或失败的检查必须如实记录。
- 不手工编辑工具生成文件；需要改变生成结果时修改源文件或生成配置。

## SHOULD：默认做法

- 保持已有目录、命名、错误处理、日志和测试风格；先复用项目已有模式。
- 优先增加可重复执行的测试和最小实现；不为假设中的未来需求增加扩展点。
- 提交前检查差异、未跟踪文件和敏感信息。

## MAY：可选做法

- 在不改变项目行为的前提下，使用更清晰的局部重构或辅助工具。

## 项目事实（初始化后补全）

补全本节后，将 frontmatter 的 `configured` 改为 `true`。如果仍有“待项目确认”项，状态查询会继续报告未配置完成。

- 主源码目录：待项目确认
- 可执行测试目录：待项目确认
- 必须通过的格式化/静态检查命令：待项目确认
- 必须通过的测试命令：待项目确认
- 生成文件和禁止手工编辑的目录：待项目确认
- 兼容性、安全和部署约束：待项目确认

## 例外记录

当前没有项目级例外。一次需求的特殊约束写入对应 `.agent/changes/<WORK编号>-<中文名称>/requirements.md`；若需要暂时放宽本文件的 `MUST`，先在这里记录：范围、理由、批准人、开始/结束日期、验证方式和回滚方案。
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
        rules_status = create_text_if_missing(
            workspace / "rules" / "always.md",
            RULES_TEMPLATE.replace("{{UPDATED_DATE}}", date.today().isoformat()),
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
    print(f"{memory_status}：{workspace / 'memory.md'}")
    print(f"{rules_status}：{workspace / 'rules' / 'always.md'}")
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
