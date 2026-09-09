#!/usr/bin/env python3
"""从 .agent 生命周期工件推导工作项状态、关系和下一步。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
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
WORKFLOW_MODES = {"full", "compact"}
LIFECYCLE_MODES = {"lite", "managed", "strict"}
MODE_LABELS = {"lite": "轻量", "managed": "受管理", "strict": "严格"}
STATUS_SCHEMA_VERSION = "1"


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


def markdown_section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    section = text[match.end() :]
    next_heading = re.search(r"^##\s+", section, re.MULTILINE)
    return section[: next_heading.start()] if next_heading else section


def markdown_table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def table_column(headers: list[str], *names: str) -> int | None:
    normalized = [header.casefold() for header in headers]
    for name in names:
        if name.casefold() in normalized:
            return normalized.index(name.casefold())
    return None


def source_coverage_status(requirements_path: Path) -> dict[str, object]:
    """Validate the optional source-to-requirement coverage table."""
    result: dict[str, object] = {
        "required": False,
        "status": "not_required",
        "level": "none",
        "path": str(requirements_path),
        "rows": 0,
        "mapped": 0,
        "unmapped": 0,
        "rich_rows": 0,
        "warnings": [],
    }
    if not requirements_path.is_file():
        return result

    fields = file_fields(requirements_path)
    if fields.get("source_coverage", "").strip().lower() != "required":
        return result

    result["required"] = True
    text = read_text(requirements_path)
    heading = re.search(r"^##\s+来源覆盖\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not heading:
        result["status"] = "incomplete"
        result["warnings"].append("requirements.md 声明需要来源覆盖，但缺少“## 来源覆盖”表格。")
        return result

    section = markdown_section(text, "来源覆盖")
    rows = markdown_table_rows(section)

    if len(rows) < 2:
        result["status"] = "incomplete"
        result["warnings"].append("来源覆盖表格没有可验证的数据行。")
        return result

    headers = rows[0]
    source_column = table_column(headers, "来源", "source")
    anchor_column = table_column(headers, "锚点", "anchor")
    requirement_column = table_column(headers, "REQ", "需求")
    acceptance_column = table_column(headers, "AC", "验收")
    status_column = table_column(headers, "状态", "status")
    if None in {source_column, anchor_column, requirement_column, acceptance_column, status_column}:
        result["status"] = "invalid"
        result["warnings"].append("来源覆盖表格必须包含来源、锚点、REQ、AC、状态列。")
        return result

    rich_columns = {
        "type": table_column(headers, "类型", "type"),
        "summary": table_column(headers, "摘要", "summary"),
        "paths": table_column(headers, "适用路径", "paths", "applies_to"),
        "verification": table_column(headers, "验证", "verification", "verify"),
    }
    rich = all(value is not None for value in rich_columns.values())
    result["level"] = "rich" if rich else "basic"
    result["rows"] = len(rows) - 1
    result["rich_rows"] = len(rows) - 1 if rich else 0
    for row in rows[1:]:
        cells = row + [""] * (len(headers) - len(row))
        source = cells[source_column].strip()
        anchor = cells[anchor_column].strip()
        requirement = cells[requirement_column].strip()
        acceptance = cells[acceptance_column].strip()
        coverage_state = cells[status_column].strip().casefold()
        mapped = bool(
            source
            and anchor
            and re.search(r"\bREQ-\d+\b", requirement, re.IGNORECASE)
            and re.search(r"\bAC-\d+\b", acceptance, re.IGNORECASE)
            and coverage_state in {"verified", "已验证", "complete", "completed"}
        )
        if mapped and rich:
            mapped = all(cells[index].strip() for index in rich_columns.values())
        if mapped:
            result["mapped"] += 1
        else:
            result["unmapped"] += 1

    if result["unmapped"]:
        result["status"] = "incomplete"
        result["warnings"].append("来源覆盖存在未读取、未定位、未映射或未验证的来源。")
    else:
        result["status"] = "complete"
    return result


def testing_evidence_status(
    report_path: Path,
    expected_acceptance_ids: set[str] | None = None,
) -> dict[str, object]:
    """Validate the optional executable evidence matrix in testing/report.md."""
    result: dict[str, object] = {
        "required": False,
        "status": "not_required",
        "path": str(report_path),
        "rows": 0,
        "passed": 0,
        "unmapped": 0,
        "covered_acceptance": [],
        "missing_acceptance": [],
        "warnings": [],
    }
    if not report_path.is_file():
        result["status"] = "missing"
        return result

    text = read_text(report_path)
    fields = frontmatter_fields(text)
    result["required"] = fields.get("evidence", "").strip().lower() == "required"
    section = "\n".join(
        markdown_section(text, heading)
        for heading in ("检查证据", "证据矩阵", "验证结果", "验收矩阵")
    )
    rows = markdown_table_rows(section or text)
    if len(rows) < 2:
        if result["required"] or expected_acceptance_ids:
            result["status"] = "incomplete"
            result["warnings"].append("验证报告缺少覆盖验收标准的结构化证据表。")
        else:
            result["status"] = "legacy"
        return result

    headers = rows[0]
    columns = {
        "check": table_column(headers, "检查项", "check", "id", "验收项"),
        "command": table_column(headers, "命令", "command", "procedure", "步骤"),
        "exit_code": table_column(headers, "退出码", "exit_code", "exit"),
        "result": table_column(headers, "结果", "result", "状态"),
        "evidence": table_column(headers, "证据", "evidence", "evidence_path"),
    }
    if any(value is None for value in columns.values()):
        result["status"] = "invalid"
        result["warnings"].append("结构化验证证据必须包含检查项、命令、退出码、结果和证据列。")
        return result

    result["rows"] = len(rows) - 1
    covered_acceptance: set[str] = set()
    for row in rows[1:]:
        cells = row + [""] * (len(headers) - len(row))
        check = cells[columns["check"]].strip()
        command = cells[columns["command"]].strip()
        exit_code = cells[columns["exit_code"]].strip().casefold()
        outcome = cells[columns["result"]].strip().casefold()
        evidence = cells[columns["evidence"]].strip()
        passed = bool(
            check
            and command
            and (re.fullmatch(r"-?\d+", exit_code) or exit_code in {"manual", "人工"})
            and outcome in {"passed", "pass", "通过", "verified", "已验证"}
            and evidence
        )
        covered_acceptance.update(
            value.upper()
            for value in re.findall(r"\bAC-\d+\b", check, re.IGNORECASE)
        )
        if passed:
            result["passed"] += 1
        else:
            result["unmapped"] += 1

    expected = {value.upper() for value in (expected_acceptance_ids or set())}
    result["covered_acceptance"] = sorted(covered_acceptance)
    result["missing_acceptance"] = sorted(expected - covered_acceptance)
    if result["missing_acceptance"]:
        result["warnings"].append(
            "验证证据未覆盖全部验收标准：" + "、".join(result["missing_acceptance"]) + "。"
        )
    if result["unmapped"] or result["missing_acceptance"]:
        result["status"] = "incomplete"
        if result["unmapped"]:
            result["warnings"].append("验证证据存在缺少命令、结果、退出码或证据位置的检查项。")
    elif report_status(report_path) == "passed":
        result["status"] = "complete"
    else:
        result["status"] = "incomplete" if result["required"] else "legacy"
    return result


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
    workflow = (requirements_fields.get("workflow") or "full").strip().lower()
    explicit_mode = (requirements_fields.get("mode") or "").strip().lower()
    if explicit_mode in LIFECYCLE_MODES:
        mode = explicit_mode
        mode_source = "requirements.md"
        mode_valid = True
    elif explicit_mode:
        mode = "strict" if workflow == "full" else "managed"
        mode_source = "workflow 兼容推导"
        mode_valid = False
    else:
        mode = "strict" if workflow == "full" else "managed"
        mode_source = "workflow 兼容推导"
        mode_valid = True
    return {
        "work_id": work_id,
        "name": name or work_dir.name,
        "workflow": workflow,
        "mode": mode,
        "mode_label": MODE_LABELS[mode],
        "mode_reason": requirements_fields.get("mode_reason", "").strip(),
        "mode_source": mode_source,
        "mode_valid": mode_valid,
        "mode_raw": explicit_mode,
        "depends_on_ids": parse_id_list(requirements_fields.get("depends_on")),
        "related_to_ids": parse_id_list(requirements_fields.get("related_to")),
    }


def requirement_acceptance_ids(requirements_path: Path) -> set[str]:
    if not requirements_path.is_file():
        return set()
    return {
        value.upper()
        for value in re.findall(
            r"\bAC-\d+\b", read_text(requirements_path), re.IGNORECASE
        )
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
    source_coverage = source_coverage_status(work_dir / "requirements.md")
    test_evidence = testing_evidence_status(
        work_dir / "testing" / "report.md",
        requirement_acceptance_ids(work_dir / "requirements.md"),
    )
    result: dict[str, object] = {
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
        "source_coverage": source_coverage,
        "test_evidence": test_evidence,
        "relations": {"depends_on": [], "dependents": [], "related": []},
        "warnings": [
            *warnings,
            *source_coverage["warnings"],
            *test_evidence["warnings"],
        ],
    }
    blocking_reasons: list[str] = []
    if source_coverage["status"] in {"incomplete", "invalid"} and phase in {
        "implementation",
        "verification",
        "completed",
    }:
        blocking_reasons.append("先补齐需求来源覆盖：逐项读取来源、记录锚点，并映射到 REQ-* 和 AC-*")
    if test_evidence["status"] in {"incomplete", "invalid"} and phase == "completed":
        blocking_reasons.append("先补齐结构化验证证据：记录命令、退出码、结果和证据位置")
    if blocking_reasons:
        result["state"] = "needs_attention" if phase == "completed" else "blocked"
        result["next_action"] = "；".join(blocking_reasons) + "。"
    return result


def inspect_work(work_dir: Path, archived: bool = False) -> dict[str, object]:
    identity = work_identity(work_dir)
    artifacts = {name: artifact_status(work_dir / f"{name}.md") for name in ARTIFACTS}
    artifacts["test_plan"] = "present" if (work_dir / "testing" / "plan.md").is_file() else "missing"
    artifacts["test_report"] = report_status(work_dir / "testing" / "report.md")
    tasks = task_counts(work_dir / "tasks.md")
    warnings: list[str] = []
    workflow = str(identity.get("workflow", "full"))
    if workflow not in WORKFLOW_MODES:
        warnings.append(f"工作项 workflow 必须为 full 或 compact，当前为 {workflow}。")
        workflow = "full"
    if not identity.get("mode_valid", True):
        warnings.append(
            f"工作项 mode 必须为 lite、managed 或 strict，当前为 {identity.get('mode_raw')}。"
        )
    if identity.get("mode_source") == "requirements.md" and not identity.get("mode_reason"):
        warnings.append("工作项没有记录 mode_reason；后续接力时建议补充一次模式判断依据。")
    expected_workflow = {"managed": "compact", "strict": "full"}.get(str(identity.get("mode")))
    if expected_workflow and workflow != expected_workflow:
        warnings.append(
            f"工作项 mode={identity['mode']} 应与 workflow={expected_workflow} 配套，当前为 {workflow}。"
        )

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
        (
            ("requirements", "需求尚未形成", "继续讨论并把已确认内容写入 requirements.md。"),
            ("tasks", "简短计划尚未确认", "基于已批准需求起草或修订 tasks.md。"),
        )
        if workflow == "compact"
        else (
            ("requirements", "需求尚未形成", "继续讨论并把已确认内容写入 requirements.md。"),
            ("proposal", "方案尚未确认", "基于已批准需求起草或修订 proposal.md。"),
            ("design", "设计尚未确认", "基于已批准方案完成 design.md。"),
            ("tasks", "任务计划尚未确认", "把已批准设计拆成可执行、可验证的 tasks.md。"),
        )
    )
    for stage_index, (phase, missing_reason, missing_action) in enumerate(stages):
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
        if any(artifacts[later[0]] != "missing" for later in stages[stage_index + 1 :]):
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


def apply_rules_gate(items: list[dict[str, object]], rules: dict[str, object]) -> None:
    """Block mutations before rules are confirmed; keep read-only verification visible."""
    if rules.get("ready") and rules.get("configured"):
        return
    implementation_message = (
        "项目常驻规范尚未确认或无效；实现、部署、迁移和数据变更前需修复并取得用户确认。"
    )
    verification_message = (
        "项目常驻规范尚未确认或无效；只能执行不依赖未知规则的只读验证，不能据此完成结算。"
    )
    for item in items:
        if item["archived"]:
            continue
        if item["phase"] == "implementation":
            if implementation_message not in item["warnings"]:
                item["warnings"].append(implementation_message)
            item["state"] = "blocked"
            item["next_action"] = "先检查项目并向用户确认项目常驻规范，再继续实现。"
        elif item["phase"] == "verification":
            if verification_message not in item["warnings"]:
                item["warnings"].append(verification_message)
        elif item["phase"] == "completed":
            if verification_message not in item["warnings"]:
                item["warnings"].append(verification_message)
            item["state"] = "needs_attention"
            item["next_action"] = "保留验证证据；确认项目常驻规范后再完成结算。"


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


def git_status(project_root: Path) -> dict[str, object]:
    """Return a small, read-only Git workspace overview."""
    result: dict[str, object] = {
        "status": "unknown",
        "branch": None,
        "head": None,
        "tracking": None,
        "changed_files": 0,
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "entries": [],
        "attribution": "unknown",
        "attribution_required": None,
        "warning": None,
    }
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "-c",
                "core.quotePath=false",
                "status",
                "--porcelain=v1",
                "--branch",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        result["warning"] = f"无法读取 Git 工作区：{error}。"
        return result

    if completed.returncode != 0:
        error = (completed.stderr or "").strip()
        if "not a git repository" in error.casefold():
            result.update(
                status="not_a_repository",
                attribution="not_applicable",
                attribution_required=False,
                warning=None,
            )
        else:
            result["warning"] = f"Git 状态读取失败：{error or f'退出码 {completed.returncode}'}。"
        return result

    lines = completed.stdout.splitlines()
    if lines and lines[0].startswith("## "):
        tracking = lines[0][3:]
        result["tracking"] = tracking
        result["branch"] = tracking.split("...", 1)[0]
    entries: list[dict[str, str]] = []
    for line in lines[1:]:
        if len(line) < 3:
            continue
        index_state, worktree_state = line[0], line[1]
        entries.append({"index": index_state, "worktree": worktree_state, "path": line[3:]})
    result["entries"] = entries
    result["changed_files"] = len(entries)
    result["staged"] = sum(entry["index"] not in {" ", "?"} for entry in entries)
    result["unstaged"] = sum(entry["worktree"] != " " for entry in entries)
    result["untracked"] = sum(
        entry["index"] == "?" and entry["worktree"] == "?" for entry in entries
    )
    head = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if head.returncode == 0:
        result["head"] = head.stdout.strip()
    result["status"] = "dirty" if entries else "clean"
    result["attribution"] = "unclassified" if entries else "none"
    result["attribution_required"] = bool(entries)
    return result


def normalize_git_path(value: str) -> str:
    return value.strip().strip('"').replace("\\", "/")


def workspace_attribution_status(work_dir: Path, git: dict[str, object]) -> dict[str, object]:
    """Match dirty Git paths to an explicit per-work-item attribution table."""
    path = work_dir / "workspace.md"
    result: dict[str, object] = {
        "status": "not_required" if git["status"] != "dirty" else "missing",
        "path": str(path),
        "base_commit": None,
        "rows": 0,
        "classified": 0,
        "unknown_paths": [],
        "warnings": [],
    }
    if git["status"] != "dirty":
        return result
    if not path.is_file():
        result["warnings"].append("Git 工作区有改动，但缺少 workspace.md 归因表。")
        return result

    text = read_text(path)
    fields = file_fields(path)
    base_commit = fields.get("base_commit")
    result["base_commit"] = base_commit
    current_head = str(git.get("head") or "")
    if current_head and base_commit and not (
        current_head.startswith(base_commit) or base_commit.startswith(current_head)
    ):
        result["status"] = "stale"
        result["warnings"].append("workspace.md 的 base_commit 与当前 HEAD 不一致，需要重新归因。")
        return result
    if current_head and not base_commit:
        result["warnings"].append("workspace.md 缺少 base_commit，无法锚定本次工作区归因。")

    section = markdown_section(text, "工作区归因") or markdown_section(text, "归因")
    rows = markdown_table_rows(section)
    if len(rows) < 2:
        result["warnings"].append("workspace.md 缺少可验证的工作区归因表。")
        return result
    headers = rows[0]
    path_column = table_column(headers, "路径", "path")
    owner_column = table_column(headers, "归属", "owner", "类别")
    note_column = table_column(headers, "说明", "note", "备注")
    if path_column is None or owner_column is None:
        result["status"] = "invalid"
        result["warnings"].append("工作区归因表必须包含路径和归属列。")
        return result

    # The attribution file records the classification and must not classify itself.
    self_attribution_path = normalize_git_path(
        f".agent/changes/{work_dir.name}/workspace.md"
    )
    entries = {
        normalize_git_path(entry["path"]): entry
        for entry in git["entries"]
        if entry["path"] and normalize_git_path(entry["path"]) != self_attribution_path
    }
    owners: dict[str, str] = {}
    allowed_owners = {"current", "current_work", "user", "user_existing", "unknown"}
    result["rows"] = len(rows) - 1
    for row in rows[1:]:
        cells = row + [""] * (len(headers) - len(row))
        source_path = normalize_git_path(cells[path_column])
        owner = cells[owner_column].strip().casefold()
        if source_path:
            owners[source_path] = owner
        elif owner:
            result["warnings"].append("工作区归因表存在缺少路径的行。")
        if note_column is not None and not cells[note_column].strip():
            result["warnings"].append(f"归因路径 {source_path} 缺少说明。")
    unknown_paths = [path for path in entries if path not in owners]
    unknown_paths.extend(
        path for path, owner in owners.items() if owner not in allowed_owners or owner == "unknown"
    )
    result["unknown_paths"] = list(dict.fromkeys(unknown_paths))
    result["classified"] = len(entries) - len([path for path in entries if path in result["unknown_paths"]])
    if result["unknown_paths"] or (current_head and not base_commit) or result["warnings"]:
        result["status"] = "incomplete" if result["status"] == "missing" else result["status"]
        if result["unknown_paths"]:
            result["warnings"].append("存在未归类或归属值无效的 Git 路径。")
    else:
        result["status"] = "complete"
    return result


def resume_read_paths(project_root: Path, item: dict[str, object]) -> list[str]:
    work_dir = Path(str(item["path"]))
    paths = [
        str(project_root / ".agent" / "rules" / "always.md"),
        str(work_dir / "requirements.md"),
    ]
    if str(item.get("workspace_attribution", {}).get("status")) in {"missing", "incomplete", "invalid", "stale"}:
        paths.append(str(work_dir / "workspace.md"))
    phase_paths = {
        "proposal": work_dir / "proposal.md",
        "design": work_dir / "design.md",
        "tasks": work_dir / "tasks.md",
        "implementation": work_dir / "tasks.md",
        "verification": work_dir / "testing" / "plan.md",
        "completed": work_dir / "testing" / "report.md",
    }
    phase_path = phase_paths.get(str(item["phase"]))
    if phase_path:
        paths.append(str(phase_path))
    if str(item["phase"]) in {"verification", "completed"}:
        paths.append(str(work_dir / "testing" / "report.md"))
    return list(dict.fromkeys(paths))


def unavailable_resume(reason: str, *, blockers: list[str] | None = None) -> dict[str, object]:
    return {
        "mode": "out_of_scope",
        "reason": reason,
        "work_item": None,
        "candidates": [],
        "blockers": blockers or [],
        "read_paths": [],
        "handoff_prompt": None,
    }


def resume_context(
    project_root: Path,
    active_items: list[dict[str, object]],
    selected_items: list[dict[str, object]],
    query: str | None,
    git: dict[str, object],
) -> dict[str, object]:
    candidate: dict[str, object] | None = None
    if query:
        if not selected_items:
            return unavailable_resume(f"未找到可恢复的工作项：{query}。")
        selected = selected_items[0]
        if selected["archived"]:
            return unavailable_resume("归档工作项只用于查阅，不能自动恢复。")
        candidate = selected
    elif len(active_items) == 1:
        candidate = active_items[0]
    elif len(active_items) > 1:
        return {
            "mode": "ask_user",
            "reason": "存在多个活动工作项，不能凭目录时间或聊天上下文猜测要恢复哪一个。",
            "work_item": None,
            "candidates": [
                {
                    "work_id": item["work_id"],
                    "name": item["name"],
                    "phase": item["phase"],
                    "state": item["state"],
                }
                for item in active_items
            ],
            "blockers": ["请明确提供 WORK-* 编号或中文工作项名称。"],
            "read_paths": [],
            "handoff_prompt": None,
        }
    else:
        return unavailable_resume("当前没有未完成的活动工作项。")

    blockers: list[str] = []
    if git["status"] == "dirty":
        attribution = candidate.get("workspace_attribution", {})
        if attribution.get("status") != "complete":
            blockers.append("Git 工作区有未完成归因；请先区分当前工作项改动、用户改动和未知改动。")
            blockers.extend(str(warning) for warning in attribution.get("warnings", []))
    elif git["status"] == "unknown":
        blockers.append(str(git["warning"] or "Git 工作区状态未知；恢复前先人工核对。"))
    if candidate["state"] not in {"ready", "in_progress"}:
        blockers.append(str(candidate["next_action"]))
    blockers.extend(str(warning) for warning in candidate["warnings"])
    blockers = list(dict.fromkeys(blockers))
    can_auto_resume = candidate["state"] in {"ready", "in_progress"} and not blockers
    mode = "auto_resume" if can_auto_resume else "ask_user"
    reason = (
        "唯一活动工作项且没有阶段、依赖或工作区阻塞，可以按当前阶段继续。"
        if can_auto_resume
        else "工作项可以定位，但恢复前需要处理确认、阻塞或工作区归因。"
    )
    work_item = {
        "work_id": candidate["work_id"],
        "name": candidate["name"],
        "phase": candidate["phase"],
        "phase_label": candidate["phase_label"],
        "state": candidate["state"],
        "mode": candidate["mode"],
        "mode_label": candidate["mode_label"],
        "mode_reason": candidate.get("mode_reason", ""),
        "next_action": candidate["next_action"],
        "workspace_attribution": candidate.get("workspace_attribution"),
    }
    return {
        "mode": mode,
        "reason": reason,
        "work_item": work_item,
        "candidates": [],
        "blockers": blockers,
        "read_paths": resume_read_paths(project_root, candidate),
        "handoff_prompt": (
            f"$project-lifecycle 继续 {candidate['work_id']}，先恢复规范和状态，再按当前阶段执行。"
        ),
    }


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
        "confirmation_required": True,
        "warnings": [],
        "notices": [],
    }
    if not path.exists():
        result["warnings"].append(
            "项目常驻规范尚未确认（缺少 .agent/rules/always.md）；请先向用户确认规则。"
        )
        result["notices"].append("首次初始化需要用户确认项目规则；确认后再创建 always.md。")
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
    if status not in {"active", "draft"}:
        result["warnings"].append("项目常驻规范的 status 必须为 active 或 draft。")
    elif status == "draft":
        result["warnings"].append("项目常驻规范仍是草案；请先向用户确认后再进入实现。")
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
    result["confirmation_required"] = not configured
    if result["ready"] and not result["configured"]:
        result["notices"].append("项目常驻规范仍有“待项目确认”项；进入开发实现前必须取得用户确认。")
    elif result["confirmation_required"] and not result["notices"]:
        result["notices"].append("项目常驻规范尚未得到用户确认；当前只能讨论和设计。")
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
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project_root": str(project_root),
        "workspace": str(workspace),
        "scope": "project",
        "catalog": None,
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
            "confirmation_required": True,
            "warnings": ["项目尚未初始化，尚无项目常驻规范。"],
            "notices": [],
        },
        "warnings": [],
        "work_items": [],
        "git": git_status(project_root),
        "resume": unavailable_resume("项目尚未初始化。"),
    }
    catalog = workspace / "PROJECT-INDEX.md"
    if catalog.is_file() and not (workspace / "changes").is_dir():
        result.update(
            scope="workspace",
            catalog=str(catalog),
            state="workspace",
            next_action="读取 PROJECT-INDEX.md，选择一个真实项目目录后再运行状态检查。",
        )
        result["rules"] = {
            "path": str(workspace / "rules" / "always.md"),
            "present": False,
            "status": "not_applicable",
            "ready": True,
            "configured": False,
            "confirmation_required": False,
            "warnings": [],
            "notices": ["外层 .agent 仅作为多仓库导航入口，不承载项目生命周期工件。"],
        }
        result["resume"] = unavailable_resume("外层工作区只负责导航，请先选择真实项目。")
        return result
    if not workspace.is_dir():
        return result

    active_dirs, archived_dirs = work_directories(workspace / "changes")
    result["rules"] = project_rules_status(workspace)
    result["warnings"].extend(result["rules"]["warnings"])
    active_items = [inspect_work(path) for path in active_dirs]
    archived_items = [inspect_work(path, archived=True) for path in archived_dirs]
    all_items = active_items + archived_items
    for item in all_items:
        item["workspace_attribution"] = workspace_attribution_status(
            Path(str(item["path"])), result["git"]
        )
    resolve_relations(all_items)
    apply_rules_gate(all_items, result["rules"])
    result["next_work_id"] = next_work_id(all_items)

    if work:
        visible_items = [select_work(all_items, work)]
    else:
        visible_items = active_items + (archived_items if include_archive else [])

    active = [
        item
        for item in active_items
        if item["phase"] != "completed" or item["state"] != "complete"
    ]
    result["work_items"] = visible_items
    if not visible_items and not all_items:
        next_action = (
            "先检查项目常驻规范并提出确认草案；可以同时描述一个新需求。"
            if not (result["rules"]["ready"] and result["rules"]["configured"])
            else "描述一个新需求；需要跨会话管理时创建带中文名称的工作项。"
        )
        result.update(
            state="idle",
            next_action=next_action,
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
    result["resume"] = resume_context(
        project_root,
        active,
        visible_items if work else [],
        work,
        result["git"],
    )
    return result


def relation_label(relation: dict[str, object]) -> str:
    if relation["missing"]:
        return f"{relation['work_id']}（未找到）"
    state = STATE_LABELS.get(str(relation["state"]), str(relation["state"]))
    return f"{relation['work_id']} {relation['name']}（{relation['phase_label']}，{state}）"


def git_status_label(git: dict[str, object]) -> str:
    labels = {
        "clean": "干净",
        "dirty": "有未归因改动",
        "not_a_repository": "不是 Git 仓库",
        "unknown": "未知",
    }
    return labels.get(str(git["status"]), str(git["status"]))


def render_resume(status: dict[str, object]) -> str:
    resume = status["resume"]
    lines = [
        f"项目：{status['project_root']}",
        f"Git：{git_status_label(status['git'])}",
        f"恢复：{resume['mode']}",
        f"原因：{resume['reason']}",
    ]
    work_item = resume["work_item"]
    if work_item:
        lines.append(
            f"工作项：{work_item['work_id']} · {work_item['name']} | "
            f"{work_item['phase_label']} | {STATE_LABELS.get(str(work_item['state']), work_item['state'])}"
        )
        lines.append(f"模式：{work_item['mode']}（{work_item['mode_label']}）")
        lines.append(f"下一步：{work_item['next_action']}")
    if resume["candidates"]:
        lines.append(
            "候选："
            + "；".join(
                f"{candidate['work_id']} {candidate['name']}（{candidate['phase']}，{candidate['state']}）"
                for candidate in resume["candidates"]
            )
        )
    lines.extend(f"阻塞：{blocker}" for blocker in resume["blockers"])
    lines.extend(f"建议读取：{path}" for path in resume["read_paths"])
    if resume["handoff_prompt"]:
        lines.append(f"接力：{resume['handoff_prompt']}")
    return "\n".join(lines)


def render_text(status: dict[str, object]) -> str:
    if status.get("scope") == "workspace":
        return "\n".join(
            [
                f"工作区：{status['project_root']}",
                f"总入口：{status['catalog']}",
                "范围：多仓库导航工作区（不承载 WORK-* 生命周期状态）",
                f"下一步：{status['next_action']}",
            ]
        )
    lines = [f"项目：{status['project_root']}", f"工作区：{status['workspace']}"]
    if not status["initialized"]:
        lines.extend(["状态：未初始化", f"下一步：{status['next_action']}"])
        return "\n".join(lines)
    rules = status["rules"]
    lines.append(f"Git：{git_status_label(status['git'])}")
    if status["git"]["warning"]:
        lines.append(f"Git 注意：{status['git']['warning']}")
    rules_label = (
        "已加载"
        if rules["ready"] and rules["configured"]
        else "已加载，等待用户确认"
        if rules["present"]
        else "等待用户确认"
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
        lines.append(f"  模式：{item['mode']}（{item['mode_label']}）")
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
    parser.add_argument("--resume", action="store_true", help="只输出可恢复上下文、阻塞和接力提示")
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
        print(render_resume(status) if args.resume else render_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
