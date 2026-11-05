#!/usr/bin/env python3
"""签署与归档 .agent 生命周期工件；不维护按轮追加的项目历史。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from pathlib import Path
import re

import project_status


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"
# 只有已经存在阶段门槛的工件需要签署；lite 短路径和 testing/plan.md 不签。
APPROVAL_ARTIFACTS = {
    "requirements": Path("requirements.md"),
    "proposal": Path("proposal.md"),
    "design": Path("design.md"),
    "tasks": Path("tasks.md"),
    "test-report": Path("testing/report.md"),
}


def load_artifact(path: Path) -> tuple[str, bool, str]:
    """读工件并记住 BOM 与换行，避免盖章时把整份文件重写成另一种风格。"""
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw.startswith(b"\xef\xbb\xbf"), "\r\n" if b"\r\n" in raw else "\n"


def save_artifact(path: Path, text: str, bom: bool) -> None:
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def stamp_frontmatter(text: str, updates: dict[str, str], newline: str) -> str:
    """就地改写 frontmatter 键值；已存在的键替换，缺失的键追加到末尾。"""
    lines = text.split(newline)
    if not lines or lines[0].strip() != "---":
        raise RuntimeError("工件缺少 YAML frontmatter，无法签署；请先补齐 frontmatter。")
    end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if end is None:
        raise RuntimeError("工件的 frontmatter 没有结束标记 ---，无法签署。")
    pending = dict(updates)
    for index in range(1, end):
        match = re.fullmatch(r"\s*([a-z_][a-z0-9_-]*)\s*:.*", lines[index], re.IGNORECASE)
        if match and match.group(1).lower() in pending:
            lines[index] = f"{match.group(1).lower()}: {pending.pop(match.group(1).lower())}"
    lines[end:end] = [f"{key}: {value}" for key, value in pending.items()]
    result = newline.join(lines)
    return result if result.endswith(newline) else result + newline


def resolve_work_dir(root: Path, work_id: str) -> Path:
    status = project_status.inspect_project(root, include_archive=True)
    wanted = work_id.strip().upper()
    matches = [item for item in status["work_items"] if str(item["work_id"]).upper() == wanted]
    if not matches:
        available = "、".join(str(item["work_id"]) for item in status["work_items"]) or "无"
        raise RuntimeError(f"找不到工作项 {wanted}；当前可用：{available}。")
    if len(matches) > 1:
        raise RuntimeError(
            f"{wanted} 匹配到多个工作项，请先合并或重命名目录："
            + "、".join(str(item["path"]) for item in matches)
        )
    return Path(str(matches[0]["path"]))


def resolve_signer(root: Path, explicit: str | None) -> str:
    """解析签署人：本次显式传入，或 `.agent/rules/always.md` 里用户确认过的 `approver`。

    只补身份，不补批准——是否批准仍由用户表述判断，模型不能凭这个默认值自行签署。
    """
    if explicit and explicit.strip():
        return explicit.strip()
    rules = root / ".agent" / "rules" / "always.md"
    if rules.is_file():
        approver = project_status.frontmatter_fields(
            rules.read_text(encoding="utf-8-sig")
        ).get("approver", "")
        if approver:
            return approver
    raise RuntimeError(
        "缺少 --by：请在 .agent/rules/always.md 的 frontmatter 写入 "
        "approver: <用户姓名>（由用户确认），或本次显式传 --by。"
    )


def approve(args: argparse.Namespace, root: Path) -> int:
    """把用户确认写成带签署人和时间戳的签署记录。

    `--artifact all` 一次签完工作项里已存在的阶段工件。
    业务验收仍要单独 `--artifact test-report`：它要求报告已是 passed。
    """
    work_dir = resolve_work_dir(root, args.work)
    args.by = resolve_signer(root, args.by)
    if args.artifact == "all":
        names = [
            name
            for name in ("requirements", "proposal", "design", "tasks")
            if (work_dir / APPROVAL_ARTIFACTS[name]).is_file()
        ]
    else:
        names = [args.artifact]
    if not names:
        raise RuntimeError(f"{work_dir} 里没有可签署的阶段工件。")

    timestamp = datetime.now().astimezone().strftime(TIMESTAMP_FORMAT)
    role = (args.role or "").strip()
    signed: list[str] = []
    for name in names:
        path = work_dir / APPROVAL_ARTIFACTS[name]
        if not path.is_file():
            raise RuntimeError(f"工件不存在，无法签署：{path}")
        text, bom, newline = load_artifact(path)
        if name == "test-report":
            current = project_status.report_status(path)
            if current != "passed":
                raise RuntimeError(
                    f"testing/report.md 当前状态为 {current}；只有 passed 的报告才能登记业务验收。"
                )
            updates = {"accepted_by": args.by, "accepted_at": timestamp}
            keys = "accepted_by / accepted_at"
            read_back = "accepted_by"
        else:
            updates = {"status": "approved", "approved_by": args.by, "approved_at": timestamp}
            updates["approver_role"] = role
            keys = "approved_by / approved_at"
            read_back = "approved_by"
        save_artifact(path, stamp_frontmatter(text, updates, newline), bom)
        fields = project_status.frontmatter_fields(path.read_text(encoding="utf-8-sig"))
        if fields.get(read_back, "") != args.by:
            raise RuntimeError(f"签署写入后回读失败：{keys} 未出现在 {path}。")
        signed.append(path.relative_to(root).as_posix())

    payload = {
        "project_root": str(root),
        "work_id": str(args.work).upper(),
        "artifact": args.artifact,
        "paths": signed,
        "signed_by": args.by,
        "role": role or None,
        "signed_at": timestamp,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for relative in signed:
            print(f"已签署：{relative}")
        print(f"审批人：{args.by}" + (f"（{role}）" if role else ""))
        print(f"时间：{timestamp}")
    return 0


def archive_completed(args: argparse.Namespace, root: Path) -> int:
    """把已完成的工作项移进 changes/archive/YYYY-MM-DD-<名称>。

    只移动目录、不改文件内容；旧路径引用由 validate 报告。
    """
    status = project_status.inspect_project(root)
    if args.work:
        items = [project_status.select_work(status["work_items"], args.work)]
    else:
        items = [
            item
            for item in status["work_items"]
            if item["phase"] == "completed"
            and item["state"] == "complete"
            and not item["archived"]
        ]
    if not items:
        print("没有可归档的工作项（只有完成沉淀且状态为已完成的工作项能归档）。")
        return 0
    archive_dir = root / ".agent" / "changes" / "archive"
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d")
    moved: list[dict[str, str]] = []
    for item in items:
        source = Path(str(item["path"]))
        if item["phase"] != "completed" or item["state"] != "complete" or item["archived"]:
            print(f"跳过 {item['work_id']}：阶段 {item['phase']}，状态 {item['state']}。")
            continue
        target = archive_dir / f"{stamp}-{source.name}"
        if target.exists():
            raise RuntimeError(f"归档目标已存在：{target}")
        archive_dir.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        moved.append(
            {
                "work_id": str(item["work_id"]),
                "from": source.relative_to(root).as_posix(),
                "to": target.relative_to(root).as_posix(),
            }
        )
    payload = {"project_root": str(root), "archived": moved}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for entry in moved:
            print(f"已归档：{entry['work_id']} → {entry['to']}")
        if moved:
            print("下一步：运行 validate 检查指向旧路径的引用。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--approve", action="store_true", help="把用户确认盖章为带签署人和时间戳的签署记录")
    parser.add_argument(
        "--artifact",
        choices=(*APPROVAL_ARTIFACTS, "all"),
        help="签署的工件；all 一次签完已存在的阶段工件；test-report 登记业务验收而不是批准",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="把已完成的工作项移入 changes/archive/（可配合 --work 只归档一个）",
    )
    parser.add_argument("--by", help="审批人姓名；省略时取 .agent/rules/always.md 的 approver，不得由模型编造")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--work", help="WORK 编号（--approve 必填；--archive 省略时归档全部已完成项）")
    parser.add_argument("--role", help="审批人角色，可选")
    args = parser.parse_args()
    try:
        root = project_status.locate_project(args.target)
        if args.approve:
            missing = [name for name in ("work", "artifact") if not getattr(args, name)]
            if missing:
                parser.error("--approve 缺少：" + ", ".join("--" + name for name in missing))
            if args.work == "maintenance":
                parser.error("--approve 必须指定真实的 --work 编号，不能使用默认的 maintenance")
            return approve(args, root)
        if args.archive:
            return archive_completed(args, root)
        parser.error("请指定 --approve 或 --archive")
    except (RuntimeError, OSError) as error:
        print(f"生命周期工件操作失败：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
