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
STATUS_SCHEMA_VERSION = "2"
# 已批准工件的签署时间戳格式；接受 `2026-09-20 14:32:07 +0800`、ISO 和纯日期。
APPROVED_AT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?: ?[+-]\d{4}|Z)?)?$"
)
# 需求追踪：`REQ-001`、`AC-006~AC-009`（第二段可省略前缀）、四种定义写法、任务行
# 单次扫描的引用模式：区间和单个 id 一起匹配，这样结果顺序与原文一致。
TRACE_REF_PATTERN = re.compile(
    r"\b(REQ|AC|TASK)-(\d+)\s*(?:[~～]\s*(?:[A-Za-z]+-)?(\d+))?", re.IGNORECASE
)
# 定义写法在真实项目里有四种，粗体可有可无，所以先取列表项、再从行首取 id。
TRACE_LIST_ITEM_PATTERN = re.compile(r"^\s*[-*]\s+(.*?)\s*$", re.MULTILINE)
TRACE_ID_AT_START = re.compile(r"^(?:\*\*)?(REQ|AC)-(\d+)\b(.*)$", re.IGNORECASE)
TRACE_TASK_PATTERN = re.compile(
    r"^###\s+(TASK-\d+)\s*\|\s*([a-z_]+)\s*\|\s*(.*)$", re.IGNORECASE | re.MULTILINE
)
DOCUMENT_LIMITS = {
    "per_file_bytes": 20_000,
    "work_item_bytes": 80_000,
    "file_count": 6,
}


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


def approval_status(work_dir: Path, artifacts: dict[str, str]) -> dict[str, object]:
    """已批准工件必须带签署人和时间戳。

    签署只由 `project-lifecycle.ps1 approve` 盖章，模型不得自行写入
    `approved_by`/`approved_at`。这里只读回事实，缺失和格式错误分开报告。

    ponytail: 缺签署不进 item["warnings"]，否则每个历史工作项都会立刻变成不可自动恢复；
    兼容期只由 validate 报告、validate --strict 拦截，旧工件按需补签。
    """
    signed: dict[str, dict[str, str]] = {}
    unsigned: list[str] = []
    invalid: list[str] = []
    for name in ARTIFACTS:
        if artifacts.get(name) != "approved":
            continue
        fields = file_fields(work_dir / f"{name}.md")
        by = fields.get("approved_by", "").strip()
        at = fields.get("approved_at", "").strip()
        if not by or not at:
            unsigned.append(name)
            continue
        if not APPROVED_AT_PATTERN.match(at):
            invalid.append(name)
            continue
        signed[name] = {
            "approved_by": by,
            "approved_at": at,
            "approver_role": fields.get("approver_role", "").strip(),
        }
    report_fields = file_fields(work_dir / "testing" / "report.md")
    accepted_by = report_fields.get("accepted_by", "").strip()
    warnings: list[str] = []
    if unsigned:
        warnings.append(
            "已批准工件缺少签署记录：" + "、".join(f"{name}.md" for name in unsigned)
            + "；请让用户通过 project-lifecycle.ps1 approve 盖章，不要由模型填写 approved_by。"
        )
    if invalid:
        warnings.append(
            "已批准工件的签署时间戳格式无效：" + "、".join(f"{name}.md" for name in invalid)
            + "；请重新运行 approve 盖章。"
        )
    return {
        "artifacts": signed,
        "unsigned": unsigned,
        "invalid": invalid,
        "acceptance": (
            {"accepted_by": accepted_by, "accepted_at": report_fields.get("accepted_at", "").strip()}
            if accepted_by
            else None
        ),
        "status": (
            "invalid"
            if invalid
            else "incomplete"
            if unsigned
            else "complete"
            if signed
            else "not_required"
        ),
        "warnings": warnings,
    }


TASK_ID_IN_TEXT = re.compile(r"((?:TASK|T)-\d+)", re.IGNORECASE)
TASK_HEADING_STATE = re.compile(
    r"^#{2,4}\s+((?:TASK|T)-\d+)\s*\|\s*([A-Za-z_-]+)\s*\|", re.IGNORECASE | re.MULTILINE
)
TASK_HEADING_PLAIN = re.compile(
    r"^(#{2,6})\s+((?:TASK|T)-\d+)\b(.*)$", re.IGNORECASE | re.MULTILINE
)
TASK_STATE_ALIASES = {
    "pending": "pending",
    "todo": "pending",
    "wait": "pending",
    "in_progress": "in_progress",
    "doing": "in_progress",
    "done": "done",
    "complete": "done",
    "completed": "done",
    "blocked": "blocked",
}


def normalize_task_id(value: str) -> str:
    match = TASK_ID_IN_TEXT.search(value)
    if not match:
        return value.strip().upper()
    prefix, number = match.group(1).upper().split("-")
    return f"TASK-{int(number):03d}" if prefix == "TASK" else f"T-{int(number):02d}"


def normalize_task_state(value: str) -> str | None:
    return TASK_STATE_ALIASES.get(value.strip().strip("`*_ ").casefold())


def parse_task_states(text: str) -> tuple[list[tuple[str, str | None]], set[str]]:
    """解析任务行的四种真实写法，返回 (id, 状态或 None) 与命中的格式。

    支持 `### TASK-001 | done | 名称`、`## T-01 名称` + 复选框小节、
    带“状态”列的表格、以及没有任何结构化任务时的散落复选框。
    """
    tasks: dict[str, str | None] = {}
    formats: set[str] = set()

    for match in TASK_HEADING_STATE.finditer(text):
        tasks.setdefault(normalize_task_id(match.group(1)), normalize_task_state(match.group(2)))
        formats.add("heading")

    headers: list[str] | None = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            headers = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) or not cell for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        head = TASK_ID_IN_TEXT.fullmatch(cells[0]) if cells else None
        if not head:
            continue
        task_id = normalize_task_id(cells[0])
        if task_id in tasks:
            continue
        state_column = next(
            (index for index, header in enumerate(headers) if header.casefold() in {"状态", "status"}),
            None,
        )
        state = (
            normalize_task_state(cells[state_column])
            if state_column is not None and state_column < len(cells)
            else None
        )
        tasks[task_id] = state
        formats.add("table")

    headings = [
        (match.start(), match.end(), len(match.group(1)))
        for match in re.finditer(r"^(#{1,6})\s+", text, re.MULTILINE)
    ]
    for match in TASK_HEADING_PLAIN.finditer(text):
        task_id = normalize_task_id(match.group(2))
        if task_id in tasks:
            continue
        level = len(match.group(1))
        body_end = next(
            (start for start, _, other_level in headings if start > match.start() and other_level <= level),
            len(text),
        )
        body = text[match.end() : body_end]
        done = len(re.findall(r"^\s*-\s*\[[xX]\]", body, re.MULTILINE))
        pending = len(re.findall(r"^\s*-\s*\[ \]", body, re.MULTILINE))
        state = "in_progress" if done and pending else "done" if done else "pending" if pending else None
        tasks[task_id] = state
        formats.add("section-checkbox")

    if not tasks:
        for index, box in enumerate(re.findall(r"^\s*-\s*\[([ xX])\]", text, re.MULTILINE), 1):
            tasks[f"<checkbox-{index}>"] = "done" if box.lower() == "x" else "pending"
            formats.add("checkbox")
    return list(tasks.items()), formats


def task_counts(path: Path) -> dict[str, object]:
    counts: dict[str, object] = {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "blocked": 0,
        "total": 0,
        "state_known": False,
        "format": "missing",
        "warnings": [],
    }
    if not path.is_file():
        return counts
    text = read_text(path)
    parsed, formats = parse_task_states(text)
    counts["format"] = "+".join(sorted(formats)) if formats else "empty"
    counts["total"] = len(parsed)
    if not parsed:
        # 文件里明明写了任务编号却一个都没解析出来，说明格式又超出解析器，
        # 不能静默当成"没有任务"——那会把未完成的工作项显示成可交付。
        if TASK_ID_IN_TEXT.search(text):
            counts["warnings"].append(
                "tasks.md 里出现任务编号，但没有任何一个能被解析；请用 `### TASK-001 | done | 名称`、"
                "带“状态”列的表格或 `## T-01 名称` + 复选框小节。"
            )
        return counts
    for _, state in parsed:
        if state:
            counts[state] += 1
    counts["state_known"] = all(state is not None for _, state in parsed)
    if not counts["state_known"]:
        unknown = sum(1 for _, state in parsed if state is None)
        counts["warnings"].append(
            f"tasks.md 有 {unknown} 个任务没有可识别状态；新任务用 `### TASK-001 | pending | 名称`，或给表格加“状态”列。"
        )
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
        # 显式声明的 REQ↔AC 直连（每行把该来源的 REQ 与 AC 配成对）；没有来源覆盖表时为空。
        "pairs": [],
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
        for requirement_id in re.findall(r"\bREQ-\d+\b", requirement, re.IGNORECASE):
            for acceptance_id in re.findall(r"\bAC-\d+\b", acceptance, re.IGNORECASE):
                pair = [normalize_trace_id(requirement_id), normalize_trace_id(acceptance_id)]
                if pair not in result["pairs"]:
                    result["pairs"].append(pair)

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
    missing_fields: list[str] = []
    for index, row in enumerate(rows[1:], 1):
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
            absent = [
                label
                for label, value in (
                    ("检查项", check),
                    ("命令", command),
                    ("证据位置", evidence),
                )
                if not value
            ]
            if exit_code not in {"manual", "人工"} and not re.fullmatch(r"-?\d+", exit_code):
                absent.append("退出码")
            if outcome not in {"passed", "pass", "通过", "verified", "已验证"}:
                absent.append("结果(需 passed)")
            missing_fields.append(
                f"第 {index} 个数据行（{check or '无检查项'}）缺：{'、'.join(absent)}"
            )

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
            detail = "；".join(missing_fields[:5])
            if len(missing_fields) > 5:
                detail += f"；另有 {len(missing_fields) - 5} 行"
            result["warnings"].append(f"验证证据存在不完整的检查项：{detail}。")
    elif report_status(report_path) == "passed":
        result["status"] = "complete"
    else:
        result["status"] = "incomplete" if result["required"] else "legacy"
    return result


def document_budget_status(work_dir: Path) -> dict[str, object]:
    """Measure primary work-item Markdown without reading evidence logs into context."""
    paths = [
        work_dir / "requirements.md",
        work_dir / "proposal.md",
        work_dir / "design.md",
        work_dir / "tasks.md",
        work_dir / "testing" / "plan.md",
        work_dir / "testing" / "report.md",
        work_dir / "workspace.md",
    ]
    files: list[dict[str, object]] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append({"path": str(path), "bytes": size})

    total_bytes = sum(int(entry["bytes"]) for entry in files)
    oversized = [
        entry for entry in files if int(entry["bytes"]) > DOCUMENT_LIMITS["per_file_bytes"]
    ]
    warnings: list[str] = []
    if oversized:
        labels = "、".join(Path(str(entry["path"])).name for entry in oversized)
        warnings.append(
            f"核心 Markdown 超过 {DOCUMENT_LIMITS['per_file_bytes']} bytes：{labels}；建议把日志和讨论移到独立证据文件。"
        )
    if total_bytes > DOCUMENT_LIMITS["work_item_bytes"]:
        warnings.append(
            f"当前工作项核心 Markdown 共 {total_bytes} bytes，超过 {DOCUMENT_LIMITS['work_item_bytes']} bytes 软阈值；恢复时只读取当前阶段内容。"
        )
    if len(files) > DOCUMENT_LIMITS["file_count"]:
        warnings.append(
            f"当前工作项有 {len(files)} 个核心 Markdown，超过 {DOCUMENT_LIMITS['file_count']} 个恢复软阈值；按阶段拆分读取。"
        )
    return {
        "status": "warning" if warnings else "ok",
        "total_bytes": total_bytes,
        "file_count": len(files),
        "files": files,
        "limits": DOCUMENT_LIMITS.copy(),
        "warnings": warnings,
    }


def verification_anchor(work_dir: Path, git: dict[str, object]) -> dict[str, object]:
    """Check whether a report still covers the current code snapshot."""
    report_path = work_dir / "testing" / "report.md"
    fields = file_fields(report_path)
    verified_commit = fields.get("verified_commit", "").strip().lower()
    verified_at = fields.get("verified_at", "").strip()
    result: dict[str, object] = {
        "status": "unknown",
        "report": str(report_path),
        "verified_commit": verified_commit or None,
        "verified_at": verified_at or None,
        "reason": "验证报告没有 verified_commit，无法把证据绑定到当前源码。",
    }
    if not report_path.is_file() or not verified_commit:
        return result
    if not re.fullmatch(r"[0-9a-f]{7,40}", verified_commit):
        result["status"] = "invalid"
        result["reason"] = "验证报告的 verified_commit 不是有效 Git 提交哈希。"
        return result
    head = str(git.get("head") or "").lower()
    if not head:
        result["reason"] = "当前无法读取 HEAD，不能核对验证锚点。"
        return result
    # 未提交改动按路径判断：并发的 .agent/ 工件写入（签署、更新历史、审查报告）
    # 不代表源码变了，不该把全部历史工作项打成 stale。
    entries = git.get("entries") or []
    dirty_sources = [
        normalize_git_path(str(entry.get("path", "")))
        for entry in entries
        if not normalize_git_path(str(entry.get("path", ""))).startswith(".agent/")
    ]
    if git.get("status") != "clean" and not entries:
        # 只知道"脏"、拿不到路径清单时不能推断脏的只是工件，按保守口径报 stale。
        result["status"] = "stale"
        result["reason"] = "工作区有未提交改动但无法取得路径清单，不能确认验证结论仍成立。"
        return result
    if head.startswith(verified_commit) or verified_commit.startswith(head):
        if dirty_sources:
            result["status"] = "drift"
            result["dirty_files"] = len(dirty_sources)
            result["reason"] = (
                f"报告绑定提交 {verified_commit[:7]}；工作区另有 {len(dirty_sources)} 个未提交源码改动"
                f"（例如 `{dirty_sources[0]}`），不在该次验证范围内。"
            )
            return result
        result["status"] = "verified"
        result["reason"] = "验证报告已绑定当前 HEAD；未提交改动只涉及 .agent/ 工件。"
        return result

    root = locate_project(work_dir)
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", f"{verified_commit}..HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff.returncode != 0:
        result["status"] = "stale"
        result["reason"] = "验证报告绑定的提交无法解析为当前仓库的历史，需要重新验证。"
        return result
    changed = [normalize_git_path(line) for line in diff.stdout.splitlines() if line.strip()]
    committed_drift = [path for path in changed if not path.startswith(".agent/")]
    if committed_drift or dirty_sources:
        # 报告覆盖的是它绑定的那个提交，之后的提交属于后续工作，不是本次证据失效。
        # 但要如实报告漂移，避免把“当时验过”读成“现在仍然成立”。
        result["status"] = "drift"
        result["committed_files"] = len(committed_drift)
        result["dirty_files"] = len(dirty_sources)
        parts = []
        if committed_drift:
            parts.append(f"之后又提交了 {len(committed_drift)} 个源码改动（例如 `{committed_drift[0]}`）")
        if dirty_sources:
            parts.append(f"工作区有 {len(dirty_sources)} 个未提交源码改动（例如 `{dirty_sources[0]}`）")
        result["reason"] = (
            f"报告绑定提交 {verified_commit[:7]}，" + "，".join(parts) + "；证据只覆盖到该提交。"
        )
        return result
    result["status"] = "verified"
    result["reason"] = "验证报告绑定的代码提交之后只有 .agent/ 工件变化。"
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


def markdown_list_lines(section: str) -> list[str]:
    return [
        line.strip()
        for line in section.splitlines()
        if re.match(r"^(?:[-*+]|\d+[.)])\s+\S", line.strip())
    ]


def resume_requirements(requirements_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "goal": "",
        "acceptance_criteria": [],
        "constraints": [],
        "goal_status": "missing",
        "warnings": [],
    }
    if not requirements_path.is_file():
        result["warnings"] = ["requirements.md 缺失，无法恢复当前任务目标、验收标准和约束。"]
        return result

    text = read_text(requirements_path)
    goal = "\n".join(
        line.strip() for line in markdown_section(text, "目标").splitlines() if line.strip()
    )
    acceptance_criteria = [
        line
        for line in markdown_list_lines(markdown_section(text, "验收标准"))
        if re.search(r"\bAC-\d+\b", line, re.IGNORECASE)
    ]
    constraints = markdown_list_lines(markdown_section(text, "约束与依赖"))
    result.update(
        goal=goal,
        acceptance_criteria=acceptance_criteria,
        constraints=constraints,
        goal_status="present" if goal else "missing",
    )
    warnings: list[str] = []
    if not goal:
        warnings.append("requirements.md 缺少可恢复的“## 目标”内容；不要根据聊天摘要臆造目标。")
    if not acceptance_criteria:
        warnings.append("requirements.md 缺少带 AC-* 的“## 验收标准”列表；恢复后先补齐验收标准。")
    result["warnings"] = warnings
    return result


def state_evidence(item: dict[str, object], git: dict[str, object]) -> dict[str, object]:
    """Describe what the status projection proves, without claiming live code completion."""
    test_status = str(item.get("test_evidence", {}).get("status", "missing"))
    recorded_tests = test_status == "complete"
    anchor = verification_anchor(Path(str(item["path"])), git)
    code_sync = str(anchor["status"])
    settled = code_sync in {"verified", "drift"}
    return {
        "source": "work_item_artifacts",
        "documented_state": item["state"],
        "documented_phase": item["phase"],
        "tasks": item.get("tasks", {}),
        "test_evidence": test_status,
        "git_status": git.get("status", "unknown"),
        "git_changed_files": git.get("changed_files", 0),
        "confidence": (
            "verified_at_commit"
            if code_sync == "verified"
            else "artifact_plus_reported_evidence"
            if recorded_tests
            else "artifact_only"
        ),
        "code_sync": code_sync,
        "reconciliation": anchor,
        "settlement_status": (
            "confirmed"
            if code_sync == "verified"
            else "confirmed_at_commit"
            if code_sync == "drift"
            else "pending_reconciliation"
        ),
        "requires_reconciliation": not settled,
        "note": (
            "验证报告已绑定当前 HEAD；状态仍需结合用户验收，不等于自动发布。"
            if code_sync == "verified"
            else "验证报告覆盖到它绑定的提交；之后的改动属于后续工作，不代表当时证据错误，但也不能当作已验证。"
            if code_sync == "drift"
            else "状态由工作项工件和已记录的测试证据推导；源码是否与工件同步仍需检查。"
            if recorded_tests
            else "状态主要由工作项工件推导；源码实际完成度和文档是否同步仍需检查。"
        ),
    }


def normalize_trace_id(value: str) -> str:
    match = re.fullmatch(r"\s*(REQ|AC|TASK)-(\d+)\s*", value, re.IGNORECASE)
    return f"{match.group(1).upper()}-{int(match.group(2)):03d}" if match else value.strip().upper()


def expand_trace_ids(text: str, prefixes: tuple[str, ...] | None = None) -> list[str]:
    """展开 `REQ-001、AC-006~AC-009` 这类引用写法，顺序与原文一致。

    区间上限按 100 截断，避免 `AC-001~AC-999` 这类笔误把节点数撑爆。
    """
    found: list[str] = []
    for match in TRACE_REF_PATTERN.finditer(text):
        prefix = match.group(1).upper()
        start = int(match.group(2))
        end = int(match.group(3)) if match.group(3) else start
        for number in range(start, min(end, start + 99) + 1):
            value = f"{prefix}-{number:03d}"
            if value not in found:
                found.append(value)
    if prefixes:
        found = [value for value in found if value.split("-")[0] in prefixes]
    return found


def trace_title(remainder: str) -> str:
    """四种定义写法都要能取到标题：

    `- **REQ-001 结果上传**：...`、`- **AC-001** 一个真实仓库...`、
    `- **AC-001**：粘贴一份...`、`- REQ-001：建立自动化...`
    """
    title = remainder.replace("**", "").strip().lstrip("：: 　").strip()
    for separator in ("：", "。", "；", "（", "("):
        if separator in title:
            title = title.split(separator)[0]
    return title.strip()[:60]


def trace_definitions(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for item in TRACE_LIST_ITEM_PATTERN.finditer(text):
        head = TRACE_ID_AT_START.match(item.group(1).strip())
        if not head:
            continue
        found.append(
            {
                "id": f"{head.group(1).upper()}-{int(head.group(2)):03d}",
                "kind": head.group(1).upper(),
                "title": trace_title(head.group(3)),
            }
        )
    return found


def traceability_status(
    work_dir: Path,
    test_evidence: dict[str, object],
    source_coverage: dict[str, object],
) -> dict[str, object]:
    """需求、验收标准和任务之间的可推导链接。

    只读取工件里真实写下的引用（`- 对应：`、`- 依赖：`），不按编号顺序推测
    REQ 与 AC 的对应关系；唯一的直连边来自显式声明的来源覆盖表。
    id 只在工作项内唯一（每个工作项都有自己的 REQ-001），所以跨工作项引用必须带 work_id。
    """
    definitions: dict[str, dict[str, str]] = {}
    requirements_path = work_dir / "requirements.md"
    if requirements_path.is_file():
        for definition in trace_definitions(read_text(requirements_path)):
            definitions[definition["id"]] = definition

    tasks: list[dict[str, object]] = []
    tasks_path = work_dir / "tasks.md"
    if tasks_path.is_file():
        text = read_text(tasks_path)
        headings = list(TRACE_TASK_PATTERN.finditer(text))
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            body = text[heading.end() : end]
            task_id = heading.group(1).upper()
            maps_to: list[str] = []
            legacy: list[str] = []
            depends_on: list[str] = []
            # `对应` 和 `依赖` 可能写在同一行，用 `；` 先切开；切不开时两个键都要各自匹配，
            # 所以这里是两个独立的 if，不是 if/elif（真实工件里两者常常同段）。
            for segment in re.split(r"[；;]", body):
                if "对应" in segment:
                    tail = segment.split("对应", 1)[1].lstrip("：: 　")
                    ids = expand_trace_ids(tail, ("REQ", "AC"))
                    maps_to.extend(ids)
                    if "旧版" in tail:
                        legacy.extend(ids)
                if "依赖" in segment:
                    tail = segment.split("依赖", 1)[1].lstrip("：: 　")
                    depends_on.extend(
                        value
                        for value in expand_trace_ids(tail, ("TASK",))
                        if value != task_id
                    )
            tasks.append(
                {
                    "id": task_id,
                    "state": heading.group(2).lower(),
                    "title": heading.group(3).strip()[:60],
                    "maps_to": maps_to,
                    "legacy": legacy,
                    "depends_on": depends_on,
                }
            )

    defined = set(definitions)
    referenced = {value for task in tasks for value in task["maps_to"]}
    acceptance_ids = sorted(value for value in defined if value.startswith("AC-"))
    covered = {
        str(value).upper() for value in (test_evidence.get("covered_acceptance") or [])
    }
    return {
        "requirements": [definitions[key] for key in sorted(definitions) if key.startswith("REQ-")],
        "acceptance": [definitions[key] for key in acceptance_ids],
        "tasks": tasks,
        "requirement_acceptance_links": source_coverage.get("pairs") or [],
        "undefined_refs": sorted(value for value in referenced if value not in defined),
        "unmapped_tasks": [task["id"] for task in tasks if not task["maps_to"]],
        "acceptance_without_evidence": [value for value in acceptance_ids if value not in covered],
    }


def plan_hygiene(
    work_dir: Path,
    mode: str,
    artifacts: dict[str, str],
    tasks: dict[str, object],
) -> list[str]:
    """计划质量提示：strict 工作项的 tasks.md 应有“评审焦点”。

    只提示不阻断，且只在实现还没收口时提示：对已经 passed 的历史工作项
    回头补计划既不会改变已发生的事，也只会把列表变成噪音。
    """
    tasks_path = work_dir / "tasks.md"
    if (
        mode != "strict"
        or artifacts.get("tasks") != "approved"
        or not tasks.get("total")
        or artifacts.get("test_report") == "passed"
        or not tasks_path.is_file()
    ):
        return []
    if "## 评审焦点" in read_text(tasks_path):
        return []
    return [
        "tasks.md 缺少“## 评审焦点”：列出规格暗示但没有任务测试覆盖的失败模式"
        "（空输入、并发、权限边界、编码、超时、重复提交等），并给每条指定归属任务与测试。"
    ]


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
    document_budget = document_budget_status(work_dir)
    approval = approval_status(work_dir, artifacts)
    traceability = traceability_status(work_dir, test_evidence, source_coverage)
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
        "document_budget": document_budget,
        "approval": approval,
        "traceability": traceability,
        "relations": {"depends_on": [], "dependents": [], "related": []},
        "warnings": [
            *warnings,
            *source_coverage["warnings"],
            *test_evidence["warnings"],
        ],
        # 只影响可读性的整理项（文档体积、任务格式），不阻断恢复也不表示事实缺失。
        "hygiene": [*document_budget["warnings"], *tasks.get("warnings", [])],
        # 计划质量建议：只在实现还没收口时提示，不改变阶段判断。
        "advice": plan_hygiene(work_dir, str(identity.get("mode", "")), artifacts, tasks),
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
    if (
        phase == "verification"
        and tasks.get("total")
        and not tasks.get("state_known")
        and artifacts.get("test_report") in {"missing", "unknown"}
    ):
        # 要判断"实现是否做完"时，读不出状态的任务台账不算证据。
        blocking_reasons.append(
            "先补全 tasks.md 的任务状态（表格加“状态”列，或改用 `### TASK-001 | done | 名称`）"
        )
    if blocking_reasons:
        result["state"] = "needs_attention" if phase == "completed" else "blocked"
        result["next_action"] = "；".join(blocking_reasons) + "。"
        # 同一件事已经在 next_action 里说了，就不再重复一遍提示。
        result["hygiene"] = [
            warning
            for warning in result["hygiene"]
            if "没有可识别状态" not in str(warning)
        ]
        result["advice"] = [
            warning
            for warning in result.get("advice", [])
            if "评审焦点" not in str(warning)
        ]
    result["state_label"] = STATE_LABELS.get(str(result["state"]), str(result["state"]))
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

    if tasks["total"] and not tasks["state_known"] and artifacts.get("test_report") == "passed":
        # 有通过的验证报告时以报告为完成证据，任务台账读不出状态只算整理项。
        pass

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
    if tasks["total"] == 0 and artifacts["test_plan"] == "missing" and report == "missing":
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
    # 链接 worktree 里 --git-dir 指向主仓库的 .git/worktrees/<名>，--git-common-dir 仍指向 .git；
    # 两者不同就说明已经隔离过，不必再问用户。
    resolved = []
    for option in ("--git-dir", "--git-common-dir"):
        probe = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", option],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if probe.returncode != 0:
            break
        resolved.append((project_root / probe.stdout.strip()).resolve())
    if len(resolved) == 2:
        result["worktree"] = {
            "linked": resolved[0] != resolved[1],
            "branch": result["branch"],
            "path": str(project_root),
        }
    result["status"] = "dirty" if entries else "clean"
    result["attribution"] = "unclassified" if entries else "none"
    result["attribution_required"] = bool(entries)
    return result


def normalize_git_path(value: str) -> str:
    value = value.strip().strip('"').replace("\\", "/")
    # porcelain 的改名条目写成 `old -> new`，只认新路径。
    if " -> " in value:
        value = value.split(" -> ", 1)[1].strip().strip('"')
    return value


def workspace_attribution_status(work_dir: Path, git: dict[str, object]) -> dict[str, object]:
    """
    工作区归因机制已按用户要求停用（2026-10-10）。

    原机制要求**每个**工作项的 `workspace.md` 都登记工作区里的**全部**未提交路径，
    成本是"工作项数 × 改动路径数"份重复登记；而它只是一张快照，HEAD 一动或文件一加
    就过期，在有并发写入时几乎立刻失效。实测收益远小于维护成本。

    停用后：未提交改动仍由 Git 自己记录；"只提交当前工作项的文件、不碰用户已有与
    未知归属的改动"这条纪律不变（见 references/update-history.md）。旧项目里已有的
    `workspace.md` 不再被校验，也不再阻止恢复。

    保留函数与返回结构，使 status / resume 的调用点无需改动；无条件返回 not_required。
    """
    return {
        "status": "not_required",
        "path": str(work_dir / "workspace.md"),
        "base_commit": None,
        "rows": 0,
        "classified": 0,
        "unknown_paths": [],
        "warnings": [],
    }


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
        "warnings": [],
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
            "warnings": [],
            "read_paths": [],
            "handoff_prompt": None,
        }
    else:
        return unavailable_resume("当前没有未完成的活动工作项。")

    blockers: list[str] = []
    requirements = resume_requirements(Path(str(candidate["path"])) / "requirements.md")
    evidence = candidate.get("state_evidence") or state_evidence(candidate, git)
    # 工作区归因机制已停用（2026-10-10）：未提交改动不再阻止恢复，由 Git 自己记录。
    if git["status"] == "unknown":
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
        "goal": requirements["goal"],
        "acceptance_criteria": requirements["acceptance_criteria"],
        "constraints": requirements["constraints"],
        "goal_status": requirements["goal_status"],
        "state_evidence": evidence,
        "document_budget": candidate.get("document_budget"),
        "approval": candidate.get("approval"),
        "next_action": candidate["next_action"],
        "workspace_attribution": candidate.get("workspace_attribution"),
    }
    resume_warnings = [str(warning) for warning in requirements["warnings"]]
    resume_warnings.extend(str(warning) for warning in candidate.get("hygiene", []))
    worktree_info = git.get("worktree") or {}
    worktree = None
    if candidate["phase"] == "implementation" and worktree_info:
        linked = bool(worktree_info.get("linked"))
        if linked:
            decision = "active"
        elif git["status"] == "clean":
            decision = "proceed"
        else:
            decision = "ask_user"
        worktree = {
            "decision": decision,
            "linked": linked,
            "branch": worktree_info.get("branch"),
            "hint": {
                "active": f"已在独立 worktree（分支 {worktree_info.get('branch')}）中，不要重复询问。",
                "proceed": "工作区干净，直接在当前目录实施并遵守单写入方约定；只有即将与另一个对话同目录写入时才需要 worktree。",
                "ask_user": "工作区有未提交改动，开始改源码前先问用户一次是否开独立 worktree；"
                "用户同意再执行 git worktree add，拒绝则在当前目录工作并遵守单写入方约定。只读调查不询问。",
            }[decision],
        }
    return {
        "mode": mode,
        "reason": reason,
        "work_item": work_item,
        "candidates": [],
        "blockers": blockers,
        "warnings": resume_warnings,
        "worktree": worktree,
        "read_paths": resume_read_paths(project_root, candidate),
        "handoff_prompt": (
            f"$project-lifecycle 继续 {candidate['work_id']}，先恢复规范和状态；"
            "以 requirements.md 中的目标、验收标准和约束为当前事实源，再按当前阶段执行。"
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
    for item in all_items:
        evidence = state_evidence(item, result["git"])
        reason = str(evidence["reconciliation"]["reason"])
        if evidence["code_sync"] == "stale":
            if reason not in item["warnings"]:
                item["warnings"].append(reason)
            if item["phase"] == "completed" and item["state"] == "complete":
                item["state"] = "needs_attention"
                item["next_action"] = "先重新核对当前源码、验收证据和验证报告，再完成结算。"
                evidence = state_evidence(item, result["git"])
        elif evidence["code_sync"] == "drift":
            # 未提交改动无法归属到具体工作项，只提示不阻塞。
            if reason not in item["hygiene"]:
                item["hygiene"].append(reason)
        item["state_evidence"] = evidence
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
        "dirty": "有未提交改动",
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
        lines.append(f"目标：{work_item.get('goal') or '缺失（先补齐 requirements.md，不要根据聊天摘要臆造）'}")
        acceptance = work_item.get("acceptance_criteria", [])
        lines.append("验收标准：" + ("；".join(str(value) for value in acceptance) or "缺失（先补齐 requirements.md）"))
        constraints = work_item.get("constraints", [])
        if constraints:
            lines.append("约束：" + "；".join(str(value) for value in constraints))
        evidence = work_item.get("state_evidence", {})
        if evidence:
            lines.append(
                f"状态依据：{evidence.get('source')} | 置信度：{evidence.get('confidence')} | "
                f"源码同步：{evidence.get('code_sync')} | 结算：{evidence.get('settlement_status')}"
            )
            lines.append(f"状态说明：{evidence.get('note')}")
        budget = work_item.get("document_budget") or {}
        if budget:
            lines.append(
                f"文档预算：{budget.get('total_bytes', 0)} bytes / {budget.get('file_count', 0)} 个核心文件"
            )
        lines.append(f"下一步：{work_item['next_action']}")
    if resume["candidates"]:
        lines.append(
            "候选："
            + "；".join(
                f"{candidate['work_id']} {candidate['name']}（{candidate['phase']}，{candidate['state']}）"
                for candidate in resume["candidates"]
            )
        )
    lines.extend(f"恢复提示：{warning}" for warning in resume.get("warnings", []))
    lines.extend(f"阻塞：{blocker}" for blocker in resume["blockers"])
    lines.extend(f"建议读取：{path}" for path in resume["read_paths"])
    if resume["handoff_prompt"]:
        lines.append(f"接力：{resume['handoff_prompt']}")
    return "\n".join(lines)


def brief_projection(status: dict[str, object]) -> dict[str, object]:
    """每轮默认视图：只保留活动工作项和下一步，避免 200KB 全量 JSON 淹没上下文。"""
    items = status.get("work_items") or []
    active = [
        item
        for item in items
        if not (item["phase"] == "completed" and item["state"] == "complete")
    ]

    def compact(item: dict[str, object]) -> dict[str, object]:
        tasks = item.get("tasks") or {}
        return {
            "work_id": item["work_id"],
            "name": item["name"],
            "phase": item["phase"],
            "phase_label": item["phase_label"],
            "state": item["state"],
            "state_label": STATE_LABELS.get(str(item["state"]), str(item["state"])),
            "mode": item["mode"],
            "next_action": item["next_action"],
            "tasks": {key: tasks.get(key, 0) for key in ("pending", "in_progress", "done", "blocked")},
            "tasks_total": tasks.get("total", 0),
            "tasks_state_known": tasks.get("state_known", False),
            "warnings": list(item.get("warnings") or []),
            "hygiene": list(item.get("hygiene") or []),
            "advice": list(item.get("advice") or []),
        }

    resume = status.get("resume") or {}
    selected = resume.get("work_item") or {}
    result: dict[str, object] = {
        "schema_version": status["schema_version"],
        "generated_at": status["generated_at"],
        "project_root": status["project_root"],
        "state": status["state"],
        "next_work_id": status["next_work_id"],
        "next_action": status["next_action"],
        "rules": {
            "present": status["rules"].get("present"),
            "status": status["rules"].get("status"),
            "ready": status["rules"].get("ready"),
            "configured": status["rules"].get("configured"),
        },
        "git": {
            "status": status["git"].get("status"),
            "branch": status["git"].get("branch"),
            "head": (status["git"].get("head") or "")[:7] or None,
        },
        "work_items": [compact(item) for item in active],
        "completed_count": len(items) - len(active),
        "resume": {
            "mode": resume.get("mode"),
            "reason": resume.get("reason"),
            "blockers": resume.get("blockers") or [],
            "work_item": (
                {
                    key: selected.get(key)
                    for key in ("work_id", "name", "phase_label", "state", "goal", "next_action")
                }
                if selected
                else None
            ),
            "handoff_prompt": resume.get("handoff_prompt"),
        },
    }
    return result


def render_brief(status: dict[str, object]) -> str:
    brief = brief_projection(status)
    rules = brief["rules"]
    git = brief["git"]
    lines = [
        f"项目：{brief['project_root']}",
        f"Git：{git_status_label(git)}"
        + (f"（{git['branch']}）" if git.get("branch") else ""),
        "规范："
        + ("就绪" if rules.get("ready") and rules.get("configured") else "未就绪，先确认 .agent/rules/always.md"),
    ]
    items = brief["work_items"]
    lines.append(f"活动工作项：{len(items)} 个" + (f"；已完成 {brief['completed_count']} 个" if brief["completed_count"] else ""))
    if not items:
        lines.append(f"下一步：{brief['next_action']}")
    for item in items:
        lines.append(f"- {item['work_id']} · {item['name']} | {item['phase_label']} | {item['state_label']}")
        lines.append(f"  下一步：{item['next_action']}")
        lines.extend(f"  阻塞：{warning}" for warning in item["warnings"])
        lines.extend(f"  提示：{warning}" for warning in item["hygiene"])
        lines.extend(f"  建议：{warning}" for warning in item.get("advice", []))
    resume = brief["resume"]
    if resume.get("blockers"):
        lines.extend(f"恢复阻塞：{blocker}" for blocker in resume["blockers"])
    if resume.get("handoff_prompt"):
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
        approval = item.get("approval") or {}
        for name, signer in sorted((approval.get("artifacts") or {}).items()):
            role = f"（{signer['approver_role']}）" if signer.get("approver_role") else ""
            lines.append(f"  签署：{name}.md 由 {signer['approved_by']}{role} 于 {signer['approved_at']}")
        if approval.get("unsigned"):
            lines.append("  签署：待补签 " + "、".join(f"{name}.md" for name in approval["unsigned"]))
        if approval.get("invalid"):
            lines.append("  签署：时间戳格式无效 " + "、".join(f"{name}.md" for name in approval["invalid"]))
        acceptance = approval.get("acceptance")
        if acceptance:
            lines.append(f"  验收：{acceptance['accepted_by']} 于 {acceptance['accepted_at']}")
        evidence = item.get("state_evidence", {})
        if evidence:
            lines.append(
                f"  代码核对：{evidence.get('code_sync')}；结算：{evidence.get('settlement_status')}"
            )
        budget = item.get("document_budget", {})
        if budget:
            lines.append(
                f"  文档：{budget.get('total_bytes', 0)} bytes / {budget.get('file_count', 0)} 个核心文件"
            )
        tasks = item["tasks"]
        if tasks.get("total"):
            lines.append(
                "  任务："
                f"待办 {tasks['pending']}，进行中 {tasks['in_progress']}，"
                f"完成 {tasks['done']}，阻塞 {tasks['blocked']}"
                + ("" if tasks.get("state_known") else f"（共 {tasks['total']} 个，部分状态未记录）")
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
        lines.extend(f"  提示：{warning}" for warning in item.get("hygiene", []))
        lines.extend(f"  建议：{warning}" for warning in item.get("advice", []))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--work", help="按 WORK 编号、中文名称或目录名查询一个工作项")
    parser.add_argument("--include-archive", action="store_true", help="同时列出已归档工作项")
    parser.add_argument("--resume", action="store_true", help="只输出可恢复上下文、阻塞和接力提示")
    parser.add_argument(
        "--brief",
        action="store_true",
        help="只输出活动工作项的精简摘要；每轮默认用这个，完整列表用不带 --brief 的 status",
    )
    parser.add_argument("--json", action="store_true", help="输出便于 Agent 读取的 JSON")
    args = parser.parse_args()
    try:
        status = inspect_project(args.target, args.work, args.include_archive)
    except RuntimeError as error:
        print(f"状态检查失败：{error}", file=sys.stderr)
        return 2
    if args.brief:
        payload = brief_projection(status)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_brief(status))
    elif args.resume and args.json:
        # `resume --json` 只给恢复上下文；之前它和 status 输出同一份 200KB 全量，
        # 文档承诺的 auto_resume/blockers 反而被淹掉。未提交文件只列前 20 个，
        # 恢复不需要整份 worktree 清单。
        git = dict(status["git"])
        entries = git.get("entries") or []
        git["entries"] = entries[:20]
        git["entries_truncated"] = max(0, len(entries) - 20)
        print(
            json.dumps(
                {
                    "schema_version": status["schema_version"],
                    "generated_at": status["generated_at"],
                    "project_root": status["project_root"],
                    "state": status["state"],
                    "next_action": status["next_action"],
                    "rules": status["rules"],
                    "git": git,
                    "resume": status["resume"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(render_resume(status) if args.resume else render_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
