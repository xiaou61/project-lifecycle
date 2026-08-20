#!/usr/bin/env python3
"""从 .agent 生命周期工件推导工作项状态、关系和下一步。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ARTIFACTS = ("requirements", "proposal", "design", "tasks")
PHASE_LABELS = {
    "requirements": "需求讨论",
    "proposal": "方案选择",
    "design": "详细设计",
    "tasks": "实施计划",
    "implementation": "开发实现",
    "verification": "测试验收",
    "completed": "完成沉淀",
}
STATE_LABELS = {
    "not_started": "尚未开始",
    "draft": "草稿",
    "awaiting_approval": "等待确认",
    "stale": "需要修订",
    "needs_attention": "需要处理",
    "ready": "可以开始",
    "in_progress": "进行中",
    "blocked": "已阻塞",
    "partial": "部分通过",
    "failed": "未通过",
    "complete": "已完成",
}
WORK_ID_PATTERN = re.compile(r"WORK-\d+", re.IGNORECASE)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise RuntimeError(f"无法读取 {path}: {error}") from error


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def frontmatter_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.fullmatch(r"\s*([a-z_][a-z0-9_-]*)\s*:\s*(.*?)\s*", line, re.IGNORECASE)
        if match:
            fields[match.group(1).lower()] = unquote(match.group(2))
    return fields


def parse_id_list(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value.strip():
        return []
    result: list[str] = []
    for item in value.split(","):
        relation_id = unquote(item).strip().upper()
        if relation_id and relation_id not in result:
            result.append(relation_id)
    return result


def file_fields(path: Path) -> dict[str, str]:
    return frontmatter_fields(read_text(path)) if path.is_file() else {}


def artifact_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return file_fields(path).get("status", "unknown").lower()


def report_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = read_text(path)
    status = frontmatter_fields(text).get("status")
    if status:
        return status.lower()
    match = re.search(r"^(?:状态|status)\s*[:：]\s*`?([a-z_]+)`?\s*$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).lower() if match else "unknown"


def task_counts(path: Path) -> dict[str, int]:
    counts = {state: 0 for state in ("pending", "in_progress", "done", "blocked")}
    if not path.is_file():
        return counts
    text = read_text(path)
    for state in re.findall(
        r"^###\s+TASK-[^|\r\n]+\|\s*(pending|in_progress|done|blocked)\s*\|",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        counts[state.lower()] += 1
    if sum(counts.values()) == 0:
        counts["done"] = len(re.findall(r"^\s*-\s*\[[xX]\]", text, re.MULTILINE))
        counts["pending"] = len(re.findall(r"^\s*-\s*\[ \]", text, re.MULTILINE))
    return counts


def work_identity(work_dir: Path) -> dict[str, object]:
    identity_fields: dict[str, str] = {}
    for artifact in ARTIFACTS:
        identity_fields = file_fields(work_dir / f"{artifact}.md")
        if identity_fields:
            break
    requirements_fields = file_fields(work_dir / "requirements.md")
    fields = {**identity_fields, **requirements_fields}
    id_match = WORK_ID_PATTERN.search(work_dir.name)
    work_id = (fields.get("work_id") or (id_match.group(0) if id_match else work_dir.name)).upper()
    name = fields.get("work")
    if not name:
        name = re.sub(r"^(?:\d{4}-\d{2}-\d{2}-)?WORK-\d+-", "", work_dir.name, flags=re.IGNORECASE)
    return {
        "work_id": work_id,
        "name": name or work_dir.name,
        "depends_on_ids": parse_id_list(requirements_fields.get("depends_on")),
        "related_to_ids": parse_id_list(requirements_fields.get("related_to")),
    }


def phase_result(
    identity: dict[str, object],
    work_dir: Path,
    archived: bool,
    phase: str,
    state: str,
    next_action: str,
    artifacts: dict[str, str],
    tasks: dict[str, int],
    warnings: list[str],
) -> dict[str, object]:
    return {
        **identity,
        "slug": work_dir.name,
        "directory": work_dir.name,
        "path": str(work_dir),
        "archived": archived,
        "phase": phase,
        "phase_label": PHASE_LABELS[phase],
        "state": state,
        "next_action": next_action,
        "artifacts": artifacts,
        "tasks": tasks,
        "relations": {"depends_on": [], "dependents": [], "related": []},
        "warnings": warnings,
    }


def inspect_work(work_dir: Path, archived: bool = False) -> dict[str, object]:
    identity = work_identity(work_dir)
    artifacts = {name: artifact_status(work_dir / f"{name}.md") for name in ARTIFACTS}
    artifacts["test_plan"] = "present" if (work_dir / "testing" / "plan.md").is_file() else "missing"
    artifacts["test_report"] = report_status(work_dir / "testing" / "report.md")
    tasks = task_counts(work_dir / "tasks.md")
    warnings: list[str] = []

    identity_paths = {
        **{name: work_dir / f"{name}.md" for name in ARTIFACTS},
        "test-plan": work_dir / "testing" / "plan.md",
        "test-report": work_dir / "testing" / "report.md",
    }
    for artifact, path in identity_paths.items():
        fields = file_fields(path)
        artifact_work_id = fields.get("work_id")
        artifact_name = fields.get("work")
        if artifact_work_id and artifact_work_id.upper() != identity["work_id"]:
            warnings.append(
                f"{artifact} 的 work_id 为 {artifact_work_id}，与工作项 {identity['work_id']} 不一致。"
            )
        if artifact_name and artifact_name != identity["name"]:
            warnings.append(
                f"{artifact} 的中文名称“{artifact_name}”与工作项“{identity['name']}”不一致。"
            )
    if WORK_ID_PATTERN.fullmatch(str(identity["work_id"])) and not re.search(
        r"[\u3400-\u9fff]", str(identity["name"])
    ):
        warnings.append("新格式工作项应使用包含中文的名称。")

    stages = (
        ("requirements", "需求尚未形成", "继续讨论并把已确认内容写入 requirements.md。"),
        ("proposal", "方案尚未确认", "基于已批准需求起草或修订 proposal.md。"),
        ("design", "设计尚未确认", "基于已批准方案完成 design.md。"),
        ("tasks", "任务计划尚未确认", "把已批准设计拆成可执行、可验证的 tasks.md。"),
    )
    for phase, missing_reason, missing_action in stages:
        status = artifacts[phase]
        if status == "approved":
            continue
        if status == "missing":
            state = "not_started"
            next_action = missing_action
        elif status == "draft":
            state = "draft" if phase == "requirements" else "awaiting_approval"
            next_action = (
                "核对待确认问题；内容收敛后请用户明确确认需求。"
                if phase == "requirements"
                else f"完善{PHASE_LABELS[phase]}，然后请用户明确确认。"
            )
        elif status == "stale":
            state = "stale"
            next_action = f"根据上游变化修订{PHASE_LABELS[phase]}并重新确认。"
        else:
            state = "needs_attention"
            next_action = f"修复 {phase}.md 的 frontmatter status，再继续。"
            warnings.append(f"{phase}.md 存在但没有可识别的 status。")
        if any(artifacts[later] != "missing" for later in ARTIFACTS[ARTIFACTS.index(phase) + 1 :]):
            warnings.append(f"{missing_reason}，但已经存在下游工件；先处理最早未满足阶段。")
        return phase_result(
            identity, work_dir, archived, phase, state, next_action, artifacts, tasks, warnings
        )

    unfinished_tasks = tasks["pending"] + tasks["in_progress"] + tasks["blocked"]
    if unfinished_tasks:
        state = "blocked" if tasks["blocked"] else "in_progress"
        next_action = (
            "先解除 blocked 任务并记录阻塞原因。"
            if tasks["blocked"]
            else "按 tasks.md 继续实现，并从实际执行结果更新任务状态。"
        )
        if artifacts["test_report"] == "passed":
            warnings.append("验证报告为 passed，但仍有未完成任务；完成任务后重新验证。")
        return phase_result(
            identity,
            work_dir,
            archived,
            "implementation",
            state,
            next_action,
            artifacts,
            tasks,
            warnings,
        )

    report = artifacts["test_report"]
    if report == "passed":
        return phase_result(
            identity,
            work_dir,
            archived,
            "completed",
            "complete",
            "核对 specs、memory 和遗留事项；需要审计轨迹时再归档该工作项。",
            artifacts,
            tasks,
            warnings,
        )
    if report in {"partial", "failed", "stale"}:
        return phase_result(
            identity,
            work_dir,
            archived,
            "verification",
            report,
            "处理失败或未验证项，并重新运行受影响的检查。",
            artifacts,
            tasks,
            warnings,
        )
    if report == "unknown":
        warnings.append("testing/report.md 存在但没有可识别的状态。")
    if sum(tasks.values()) == 0 and artifacts["test_plan"] == "missing" and report == "missing":
        return phase_result(
            identity,
            work_dir,
            archived,
            "implementation",
            "ready",
            "按已批准 tasks.md 实现；完成后进入测试验收。",
            artifacts,
            tasks,
            warnings,
        )
    return phase_result(
        identity,
        work_dir,
        archived,
        "verification",
        "ready" if report == "missing" else "needs_attention",
        "建立或核对测试计划，执行检查，并据实更新 testing/report.md。",
        artifacts,
        tasks,
        warnings,
    )


def relation_summary(item: dict[str, object]) -> dict[str, object]:
    return {
        "work_id": item["work_id"],
        "name": item["name"],
        "phase": item["phase"],
        "phase_label": item["phase_label"],
        "state": item["state"],
        "archived": item["archived"],
        "missing": False,
    }


def missing_relation(work_id: str) -> dict[str, object]:
    return {
        "work_id": work_id,
        "name": None,
        "phase": None,
        "phase_label": None,
        "state": "missing",
        "archived": False,
        "missing": True,
    }


def dependency_cycles(items: list[dict[str, object]], index: dict[str, list[dict[str, object]]]) -> list[list[str]]:
    graph: dict[str, list[str]] = {}
    for item in items:
        work_id = str(item["work_id"])
        graph[work_id] = [
            dependency
            for dependency in item["depends_on_ids"]
            if dependency in index and len(index[dependency]) == 1
        ]

    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []
    cycle_keys: set[tuple[str, ...]] = set()

    def visit(work_id: str) -> None:
        state[work_id] = 1
        stack.append(work_id)
        for dependency in graph.get(work_id, []):
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state.get(dependency) == 1:
                start = stack.index(dependency)
                cycle = stack[start:] + [dependency]
                key = tuple(sorted(set(cycle)))
                if key not in cycle_keys:
                    cycle_keys.add(key)
                    cycles.append(cycle)
        stack.pop()
        state[work_id] = 2

    for work_id in graph:
        if state.get(work_id, 0) == 0:
            visit(work_id)
    return cycles


def resolve_relations(items: list[dict[str, object]]) -> None:
    index: dict[str, list[dict[str, object]]] = {}
    for item in items:
        index.setdefault(str(item["work_id"]), []).append(item)

    for work_id, duplicates in index.items():
        if len(duplicates) > 1:
            for item in duplicates:
                item["warnings"].append(f"工作项编号重复：{work_id}；请先修复编号再建立关系。")

    related_pairs: set[tuple[str, str]] = set()
    for item in items:
        source_id = str(item["work_id"])
        unresolved: list[str] = []
        for dependency_id in item["depends_on_ids"]:
            if dependency_id == source_id:
                item["warnings"].append("工作项不能依赖自身。")
            targets = index.get(dependency_id, [])
            if len(targets) != 1:
                item["relations"]["depends_on"].append(missing_relation(dependency_id))
                unresolved.append(dependency_id)
                reason = "不存在" if not targets else "编号重复"
                item["warnings"].append(f"硬依赖 {dependency_id} {reason}。")
                continue
            target = targets[0]
            item["relations"]["depends_on"].append(relation_summary(target))
            target["relations"]["dependents"].append(relation_summary(item))
            if target["phase"] != "completed" or target["state"] != "complete":
                unresolved.append(dependency_id)

        for related_id in item["related_to_ids"]:
            if related_id == source_id:
                item["warnings"].append("工作项不能关联自身。")
                continue
            targets = index.get(related_id, [])
            if len(targets) != 1:
                item["relations"]["related"].append(missing_relation(related_id))
                reason = "不存在" if not targets else "编号重复"
                item["warnings"].append(f"关联工作项 {related_id} {reason}。")
                continue
            pair = tuple(sorted((source_id, related_id)))
            if pair in related_pairs:
                continue
            related_pairs.add(pair)
            target = targets[0]
            item["relations"]["related"].append(relation_summary(target))
            target["relations"]["related"].append(relation_summary(item))

        if unresolved:
            names = "、".join(unresolved)
            if item["phase"] in {"implementation", "verification", "completed"}:
                item["state"] = "blocked" if item["phase"] != "completed" else "needs_attention"
                item["next_action"] = f"先完成或修复硬依赖：{names}。"
            else:
                item["warnings"].append(f"进入开发实现前必须完成硬依赖：{names}。")

    for cycle in dependency_cycles(items, index):
        message = f"硬依赖形成循环：{' -> '.join(cycle)}。"
        for work_id in set(cycle):
            for item in index.get(work_id, []):
                if message not in item["warnings"]:
                    item["warnings"].append(message)
                item["state"] = "blocked"
                item["next_action"] = "合并无法独立验收的需求，或抽出共同前置工作项以解除循环依赖。"

    for item in items:
        for relation_type in ("depends_on", "dependents", "related"):
            for relation in item["relations"][relation_type]:
                targets = index.get(str(relation["work_id"]), [])
                if len(targets) == 1:
                    relation.update(relation_summary(targets[0]))


def locate_project(start: Path) -> Path:
    resolved = start.resolve()
    if resolved.name == ".agent" and resolved.is_dir():
        return resolved.parent
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".agent").is_dir():
            return candidate
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return resolved


def work_directories(changes: Path) -> tuple[list[Path], list[Path]]:
    if not changes.is_dir():
        return [], []
    active = sorted(
        (
            path
            for path in changes.iterdir()
            if path.is_dir() and path.name != "archive" and not path.name.startswith(".")
        ),
        key=lambda path: path.name,
    )
    archive = changes / "archive"
    archived = [] if not archive.is_dir() else sorted(
        (path for path in archive.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.name,
    )
    return active, archived


def project_rules_status(workspace: Path) -> dict[str, object]:
    path = workspace / "rules" / "always.md"
    result: dict[str, object] = {
        "path": str(path),
        "present": path.is_file(),
        "status": "missing",
        "ready": False,
        "configured": False,
        "warnings": [],
        "notices": [],
    }
    if not path.exists():
        result["warnings"].append("缺少项目常驻规范 .agent/rules/always.md。")
        return result
    if not path.is_file():
        result["warnings"].append(".agent/rules/always.md 存在但不是文件。")
        return result

    text = read_text(path)
    fields = frontmatter_fields(text)
    # Plain Markdown rules written before this schema may omit frontmatter;
    # a clear MUST section is enough to load them safely.
    status = fields.get("status", "active").lower()
    result["status"] = status
    if not text.split("---", 2)[-1].strip():
        result["warnings"].append("项目常驻规范文件为空。")
    if status != "active":
        result["warnings"].append("项目常驻规范的 status 必须为 active。")
    if not re.search(r"^##\s+.*MUST", text, re.IGNORECASE | re.MULTILINE):
        result["warnings"].append("项目常驻规范缺少 MUST 章节。")
    placeholders = "待项目确认" in text
    configured_field = fields.get("configured")
    if configured_field is None:
        configured = not placeholders
    elif configured_field.lower() in {"true", "yes", "1"}:
        configured = not placeholders
        if placeholders:
            result["warnings"].append("项目常驻规范标记为 configured=true，但仍有“待项目确认”项。")
    elif configured_field.lower() in {"false", "no", "0"}:
        configured = False
    else:
        configured = False
        result["warnings"].append("项目常驻规范的 configured 必须为 true 或 false。")
    result["ready"] = not result["warnings"]
    result["configured"] = configured
    if result["ready"] and not result["configured"]:
        result["notices"].append("项目常驻规范仍有“待项目确认”项；进入开发实现前补全受影响的项目事实。")
    return result


def next_work_id(items: list[dict[str, object]]) -> str:
    numbers = []
    for item in items:
        match = re.fullmatch(r"WORK-(\d+)", str(item["work_id"]), re.IGNORECASE)
        if match:
            numbers.append(int(match.group(1)))
    number = max(numbers, default=0) + 1
    return f"WORK-{number:03d}"


def select_work(items: list[dict[str, object]], query: str) -> dict[str, object]:
    normalized = query.strip().casefold()

    def values(item: dict[str, object]) -> tuple[str, ...]:
        return tuple(str(item[field]).casefold() for field in ("work_id", "name", "directory"))

    exact = [item for item in items if normalized in values(item)]
    if len(exact) == 1:
        return exact[0]
    partial = [item for item in items if any(normalized in value for value in values(item))]
    matches = exact or partial
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"未找到工作项：{query}")
    labels = "、".join(f"{item['work_id']} {item['name']}" for item in matches)
    raise RuntimeError(f"工作项名称不唯一：{query}；匹配到 {labels}")


def inspect_project(
    start: Path,
    work: str | None = None,
    include_archive: bool = False,
) -> dict[str, object]:
    if not start.exists():
        raise RuntimeError(f"目标路径不存在：{start}")
    project_root = locate_project(start)
    workspace = project_root / ".agent"
    result: dict[str, object] = {
        "project_root": str(project_root),
        "workspace": str(workspace),
        "initialized": workspace.is_dir(),
        "state": "uninitialized",
        "next_work_id": None,
        "next_action": "初始化 .agent 工作区，然后从需求讨论开始。",
        "rules": {
            "path": str(project_root / ".agent" / "rules" / "always.md"),
            "present": False,
            "status": "missing",
            "ready": False,
            "configured": False,
            "warnings": ["项目尚未初始化，尚无项目常驻规范。"],
            "notices": [],
        },
        "warnings": [],
        "work_items": [],
    }
    if not workspace.is_dir():
        return result

    active_dirs, archived_dirs = work_directories(workspace / "changes")
    result["rules"] = project_rules_status(workspace)
    result["warnings"].extend(result["rules"]["warnings"])
    active_items = [inspect_work(path) for path in active_dirs]
    archived_items = [inspect_work(path, archived=True) for path in archived_dirs]
    all_items = active_items + archived_items
    resolve_relations(all_items)
    result["next_work_id"] = next_work_id(all_items)

    if work:
        visible_items = [select_work(all_items, work)]
    else:
        visible_items = active_items + (archived_items if include_archive else [])

    active = [item for item in active_items if item["phase"] != "completed"]
    result["work_items"] = visible_items
    if not visible_items and not all_items:
        result.update(
            state="idle",
            next_action="描述一个新需求；需要跨会话管理时创建带中文名称的工作项。",
        )
    elif work:
        selected = visible_items[0]
        result.update(
            state="archived" if selected["archived"] else "active",
            next_action=selected["next_action"],
        )
    elif len(active) == 1:
        result.update(state="active", next_action=active[0]["next_action"])
    elif len(active) > 1:
        result.update(state="multiple", next_action="根据中文名称或 WORK 编号选择工作项；无法确定时只问一次。")
    else:
        result.update(state="idle", next_action="开始新工作项，或按项目需要归档已完成工作项。")
    return result


def relation_label(relation: dict[str, object]) -> str:
    if relation["missing"]:
        return f"{relation['work_id']}（未找到）"
    state = STATE_LABELS.get(str(relation["state"]), str(relation["state"]))
    return f"{relation['work_id']} {relation['name']}（{relation['phase_label']}，{state}）"


def render_text(status: dict[str, object]) -> str:
    lines = [f"项目：{status['project_root']}", f"工作区：{status['workspace']}"]
    if not status["initialized"]:
        lines.extend(["状态：未初始化", f"下一步：{status['next_action']}"])
        return "\n".join(lines)
    rules = status["rules"]
    rules_label = (
        "已加载"
        if rules["ready"] and rules["configured"]
        else "已加载，待补全"
        if rules["ready"]
        else "需要处理"
    )
    lines.append(f"项目规范：{rules_label}（{rules['path']}）")
    lines.extend(f"规范注意：{warning}" for warning in rules["warnings"])
    lines.extend(f"规范提示：{notice}" for notice in rules["notices"])
    items = status["work_items"]
    if not items:
        lines.extend(
            [
                "状态：空闲",
                f"下一个工作项编号：{status['next_work_id']}",
                f"下一步：{status['next_action']}",
            ]
        )
        return "\n".join(lines)
    lines.append(f"工作项：{len(items)} 个")
    for item in items:
        state_label = STATE_LABELS.get(str(item["state"]), str(item["state"]))
        archive_label = " | 已归档" if item["archived"] else ""
        lines.append(
            f"- {item['work_id']} · {item['name']} | {item['phase_label']} | {state_label}{archive_label}"
        )
        tasks = item["tasks"]
        if sum(tasks.values()):
            lines.append(
                "  任务："
                f"待办 {tasks['pending']}，进行中 {tasks['in_progress']}，"
                f"完成 {tasks['done']}，阻塞 {tasks['blocked']}"
            )
        relations = item["relations"]
        if relations["depends_on"]:
            lines.append("  依赖：" + "；".join(relation_label(value) for value in relations["depends_on"]))
        if relations["dependents"]:
            lines.append("  被依赖：" + "；".join(relation_label(value) for value in relations["dependents"]))
        if relations["related"]:
            lines.append("  相关：" + "；".join(relation_label(value) for value in relations["related"]))
        lines.append(f"  下一步：{item['next_action']}")
        lines.extend(f"  注意：{warning}" for warning in item["warnings"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--work", help="按 WORK 编号、中文名称或目录名查询一个工作项")
    parser.add_argument("--include-archive", action="store_true", help="同时列出已归档工作项")
    parser.add_argument("--json", action="store_true", help="输出便于 Agent 读取的 JSON")
    args = parser.parse_args()
    try:
        status = inspect_project(args.target, args.work, args.include_archive)
    except RuntimeError as error:
        print(f"状态检查失败：{error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(render_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
