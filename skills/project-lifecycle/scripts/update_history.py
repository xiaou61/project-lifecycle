#!/usr/bin/env python3
"""读取、追加和检查项目的 .agent/history/updates.md。"""

from __future__ import annotations

import argparse
from datetime import date
import json
import subprocess
import sys
from pathlib import Path
import re

import project_status


HISTORY_RELATIVE = Path(".agent/history/updates.md")


def history_path(target: Path) -> Path:
    root = project_status.locate_project(target)
    path = root / HISTORY_RELATIVE
    if not path.is_file():
        raise RuntimeError(f"缺少更新历史：{path}；请先运行 project-lifecycle.ps1 init。")
    return path


def history_entries(text: str) -> list[str]:
    return ["## " + chunk for chunk in re.split(r"\n## (?=\d{4}-\d{2}-\d{2} · )", text)[1:]]


def list_history(path: Path, tail: int | None, as_json: bool) -> int:
    values = history_entries(path.read_text(encoding="utf-8-sig"))
    if tail is not None:
        values = values[-tail:] if tail else []
    if as_json:
        print(json.dumps({"path": str(path), "entries": values}, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(values) if values else "当前没有更新记录。")
    return 0


def append_record(args: argparse.Namespace, path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig")
    if "当前暂无更新记录。" in text:
        text = text.replace("当前暂无更新记录。", "", 1).rstrip()
    record = f"""
## {date.today().isoformat()} · {args.work} · {args.title}

- 类型：{args.type}
- 变更：{args.change}
- 决策：{args.decision}
- 依据：{args.basis}
- 验证：{args.verification}
- 本地提交：{args.local_commit}
- 远端推送：{args.remote_push}
"""
    path.write_text(text.rstrip() + "\n" + record, encoding="utf-8", newline="\n")
    print(f"已追加更新记录：{path}")
    return 0


def git_checkpoint(root: Path, as_json: bool) -> int:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "无法读取 Git 工作区状态。")
    dirty = bool(result.stdout.strip())
    payload = {
        "project_root": str(root),
        "status": "needs_commit" if dirty else "clean",
        "dirty": dirty,
        "message": "存在未提交改动，需要先归因并形成本地检查点。" if dirty else "工作区干净，当前没有待提交改动。",
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"本地检查点：{'需要提交' if dirty else '工作区干净'}")
        print(payload["message"])
    return 1 if dirty else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--list", action="store_true", help="查看更新历史")
    parser.add_argument("--record", action="store_true", help="追加一条更新记录")
    parser.add_argument("--check", action="store_true", help="检查本地 Git 提交检查点")
    parser.add_argument("--tail", type=int, help="只查看最近 N 条记录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--work", default="maintenance", help="WORK 编号或 maintenance")
    parser.add_argument("--title", help="记录标题")
    parser.add_argument("--type", choices=("implementation", "decision", "verification", "maintenance"), default="maintenance")
    parser.add_argument("--change", help="本轮变更")
    parser.add_argument("--decision", help="本轮决策")
    parser.add_argument("--basis", help="依据路径或事实")
    parser.add_argument("--verification", help="实际验证和结果")
    parser.add_argument("--local-commit", default="待用户授权/未提交")
    parser.add_argument("--remote-push", default="未执行")
    args = parser.parse_args()
    try:
        root = project_status.locate_project(args.target)
        if args.check:
            return git_checkpoint(root, args.json)
        path = history_path(args.target)
        if args.record:
            required = {
                "title": args.title,
                "change": args.change,
                "decision": args.decision,
                "basis": args.basis,
                "verification": args.verification,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                parser.error("--record 缺少：" + ", ".join("--" + name.replace("_", "-") for name in missing))
            return append_record(args, path)
        return list_history(path, args.tail, args.json)
    except (RuntimeError, OSError) as error:
        print(f"更新历史操作失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
