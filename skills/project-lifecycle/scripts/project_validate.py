#!/usr/bin/env python3
"""严格校验 .agent 生命周期工件的结构、引用和证据。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path

import project_status


SCHEMA_VERSION = project_status.STATUS_SCHEMA_VERSION
CORE_REQUIREMENT_HEADINGS = ("目标", "验收标准")
DECISION_HEADINGS = ("已确认事实", "用户决定", "实现选择", "待确认问题")
SEVERE_WARNING_MARKERS = (
    "硬依赖",
    "循环",
    "work_id",
    "中文名称",
    "下游工件",
    "来源覆盖",
    "workspace.md",
    "归因",
)


def issue(work_id: str | None, message: str) -> dict[str, str | None]:
    return {"work_id": work_id, "message": message}


def heading_present(text: str, heading: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE))


def defined_ids(text: str, prefix: str) -> list[str]:
    if prefix == "TASK":
        pattern = r"^###\s+(TASK-\d+)\s+\|"
    else:
        pattern = rf"^\s*(?:[-*]\s+)?({prefix}-\d+)\s*[:：|]"
    return [value.upper() for value in re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)]


def duplicate_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_artifact_sections(item: dict[str, object], warnings: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    errors: list[dict[str, str | None]] = []
    work_id = str(item["work_id"])
    work_dir = Path(str(item["path"]))
    requirements = work_dir / "requirements.md"
    if requirements.is_file() and item["artifacts"]["requirements"] == "approved":
        text = requirements.read_text(encoding="utf-8-sig")
        for heading in CORE_REQUIREMENT_HEADINGS:
            if not heading_present(text, heading):
                errors.append(issue(work_id, f"requirements.md 已批准但缺少“## {heading}”章节。"))
        missing_decisions = [heading for heading in DECISION_HEADINGS if not heading_present(text, heading)]
        if missing_decisions:
            warnings.append(issue(work_id, "requirements.md 缺少决策分层章节：" + "、".join(missing_decisions) + "。"))

    for artifact_name, status in item["artifacts"].items():
        if status == "unknown":
            errors.append(issue(work_id, f"{artifact_name} 工件存在但 frontmatter status 无法识别。"))

    for prefix, artifact_name in (("REQ", "requirements"), ("AC", "requirements"), ("TASK", "tasks")):
        path = work_dir / f"{artifact_name}.md"
        if not path.is_file():
            continue
        values = defined_ids(path.read_text(encoding="utf-8-sig"), prefix)
        for duplicate in duplicate_ids(values):
            errors.append(issue(work_id, f"{artifact_name}.md 中 {duplicate} 重复定义。"))
    return errors


def validate_source_references(item: dict[str, object]) -> list[dict[str, str | None]]:
    source = item.get("source_coverage", {})
    if not source.get("required"):
        return []
    requirements_path = Path(str(source["path"]))
    if not requirements_path.is_file():
        return []
    text = requirements_path.read_text(encoding="utf-8-sig")
    requirement_ids = {
        value.upper() for value in re.findall(r"\bREQ-\d+\b", text, re.IGNORECASE)
    }
    acceptance_ids = {
        value.upper() for value in re.findall(r"\bAC-\d+\b", text, re.IGNORECASE)
    }
    section = project_status.markdown_section(text, "来源覆盖")
    rows = project_status.markdown_table_rows(section)
    if len(rows) < 2:
        return []
    req_column = project_status.table_column(rows[0], "REQ", "需求")
    ac_column = project_status.table_column(rows[0], "AC", "验收")
    if req_column is None or ac_column is None:
        return []
    errors: list[dict[str, str | None]] = []
    for row in rows[1:]:
        cells = row + [""] * (len(rows[0]) - len(row))
        for prefix, column, defined in (("REQ", req_column, requirement_ids), ("AC", ac_column, acceptance_ids)):
            for value in re.findall(rf"\b{prefix}-\d+\b", cells[column], re.IGNORECASE):
                if value.upper() not in defined:
                    errors.append(issue(str(item["work_id"]), f"来源覆盖引用了未定义的 {value.upper()}。"))
    return errors


def validate_item(
    item: dict[str, object],
    git: dict[str, object],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    errors: list[dict[str, str | None]] = []
    warnings: list[dict[str, str | None]] = []
    work_id = str(item["work_id"])
    errors.extend(validate_artifact_sections(item, warnings))
    errors.extend(validate_source_references(item))

    for warning in item["warnings"]:
        message = str(warning)
        if any(marker in message for marker in SEVERE_WARNING_MARKERS):
            errors.append(issue(work_id, message))
        else:
            warnings.append(issue(work_id, message))

    source = item.get("source_coverage", {})
    if source.get("status") in {"incomplete", "invalid"}:
        errors.append(issue(work_id, "需求来源覆盖未完成：" + "；".join(source.get("warnings", []))))
    elif source.get("required") and source.get("level") == "basic":
        warnings.append(issue(work_id, "来源覆盖仍是 basic 格式；严格校验建议补充类型、摘要、适用路径和验证列。"))

    evidence = item.get("test_evidence", {})
    if evidence.get("status") in {"incomplete", "invalid"}:
        errors.append(issue(work_id, "结构化测试证据不完整：" + "；".join(evidence.get("warnings", []))))
    elif evidence.get("status") == "legacy" and item["artifacts"]["test_report"] == "passed":
        warnings.append(issue(work_id, "验证报告为 passed，但仍使用未结构化的旧格式。"))
    if item["artifacts"]["test_report"] in {"partial", "failed", "stale"}:
        errors.append(issue(work_id, f"验证报告状态为 {item['artifacts']['test_report']}，不能作为完成证据。"))

    attribution = item.get("workspace_attribution", {})
    if git["status"] == "dirty" and attribution.get("status") != "complete":
        errors.append(issue(work_id, "Git 工作区改动尚未完成该工作项的 workspace.md 归因。"))
    return errors, warnings


def validate_project(start: Path, *, include_archive: bool = False, strict: bool = False) -> dict[str, object]:
    status = project_status.inspect_project(start, include_archive=include_archive)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project_root": status["project_root"],
        "scope": status["scope"],
        "strict": strict,
        "valid": True,
        "errors": [],
        "warnings": [],
        "work_items": [],
    }
    if status["scope"] == "workspace":
        result["errors"].append(issue(None, "当前路径是多仓库导航工作区，请对真实项目运行校验。"))
        result["valid"] = False
        return result
    if not status["initialized"]:
        result["errors"].append(issue(None, "项目尚未初始化 .agent 工作区。"))
        result["valid"] = False
        return result

    result["warnings"].extend(issue(None, str(warning)) for warning in status["warnings"])
    if not status["rules"]["ready"] or not status["rules"]["configured"]:
        result["errors"].append(issue(None, "项目常驻规范未确认或无效。"))

    for item in status["work_items"]:
        errors, warnings = validate_item(item, status["git"])
        result["errors"].extend(errors)
        result["warnings"].extend(warnings)
        result["work_items"].append(
            {
                "work_id": item["work_id"],
                "phase": item["phase"],
                "state": item["state"],
                "errors": len(errors),
                "warnings": len(warnings),
            }
        )
    result["valid"] = not result["errors"] and (not strict or not result["warnings"])
    return result


def render_text(result: dict[str, object]) -> str:
    lines = [
        f"项目：{result['project_root']}",
        f"严格模式：{'是' if result['strict'] else '否'}",
        f"结果：{'通过' if result['valid'] else '未通过'}",
    ]
    lines.extend(f"错误：{value['work_id'] or '项目'}：{value['message']}" for value in result["errors"])
    lines.extend(f"警告：{value['work_id'] or '项目'}：{value['message']}" for value in result["warnings"])
    if not result["errors"] and not result["warnings"]:
        lines.append("未发现结构、引用或证据问题。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--include-archive", action="store_true", help="同时校验已归档工作项")
    parser.add_argument("--strict", action="store_true", help="把警告也视为失败")
    parser.add_argument("--json", action="store_true", help="输出便于 Agent 读取的 JSON")
    args = parser.parse_args()
    try:
        result = validate_project(args.target, include_archive=args.include_archive, strict=args.strict)
    except (RuntimeError, OSError) as error:
        print(f"严格校验失败：{error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
