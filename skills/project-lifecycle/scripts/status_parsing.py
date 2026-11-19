#!/usr/bin/env python3
"""project_status 的文本/任务解析层：frontmatter、任务状态、Markdown 表格、追踪引用。

纯函数层，不依赖 Git 与编排逻辑；从 project_status.py 抽出以便单测和复用。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from status_schema import APPROVED_AT_PATTERN, ARTIFACTS


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


def approval_status(work_dir: Path, artifacts: dict[str, str]) -> dict[str, Any]:
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


def task_counts(path: Path) -> dict[str, Any]:
    counts: dict[str, Any] = {
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
