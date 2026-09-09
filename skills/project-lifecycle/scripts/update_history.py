#!/usr/bin/env python3
"""读取、追加和检查项目的 .agent/history/updates.md。"""

from __future__ import annotations

import argparse
from datetime import datetime
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
    heading = r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2}(?: [+-]\d{4})?)? · "
    return ["## " + chunk for chunk in re.split(rf"\n## (?={heading})", text)[1:]]


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
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    record = f"""
## {timestamp} · {args.work} · {args.title}

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


def git_command(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def recorded_remote_commit(path: Path, remote_commit: str) -> str | None:
    if not path.is_file():
        return None
    remote_commit = remote_commit.lower()
    for entry in reversed(history_entries(path.read_text(encoding="utf-8-sig"))):
        for line in entry.splitlines():
            if not re.match(r"^\s*-\s*远端推送：", line):
                continue
            for value in re.findall(r"\b[0-9a-f]{7,40}\b", line, re.IGNORECASE):
                if remote_commit.startswith(value.lower()):
                    return value.lower()
    return None


def push_status(root: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "project_root": str(root),
        "remote": None,
        "branch": None,
        "local_commit": None,
        "remote_commit": None,
        "status": "unknown",
        "history_status": "missing",
        "history_commit": None,
        "consistent": False,
        "warning": None,
    }
    branch = git_command(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = git_command(root, "rev-parse", "--verify", "HEAD")
    if branch.returncode != 0 or head.returncode != 0:
        result["warning"] = "无法读取当前分支或 HEAD，不能核对远端。"
        return result
    branch_name = branch.stdout.strip()
    local_commit = head.stdout.strip().lower()
    result["branch"] = branch_name
    result["local_commit"] = local_commit

    remote = git_command(root, "config", "--get", f"branch.{branch_name}.remote")
    remote_name = remote.stdout.strip() if remote.returncode == 0 else ""
    if not remote_name:
        remotes = git_command(root, "remote")
        remote_name = next((line.strip() for line in remotes.stdout.splitlines() if line.strip()), "")
    if not remote_name:
        result["status"] = "no_remote"
        result["warning"] = "当前仓库没有可查询的远端。"
        return result
    result["remote"] = remote_name

    queried = git_command(root, "ls-remote", "--heads", remote_name, f"refs/heads/{branch_name}")
    if queried.returncode != 0:
        result["warning"] = "远端查询失败；请检查网络、凭据和远端配置。"
        return result
    line = next((line for line in queried.stdout.splitlines() if line.strip()), "")
    if not line:
        result["status"] = "not_pushed"
        result["warning"] = f"远端不存在分支 {branch_name}。"
        return result
    remote_commit = line.split()[0].lower()
    result["remote_commit"] = remote_commit
    result["status"] = "up_to_date" if remote_commit == local_commit else "mismatch"

    history = root / HISTORY_RELATIVE
    history_commit = recorded_remote_commit(history, remote_commit)
    result["history_commit"] = history_commit
    result["history_status"] = "recorded" if history_commit else "missing"
    result["consistent"] = result["status"] == "up_to_date" and bool(history_commit)
    if result["status"] == "up_to_date" and not history_commit:
        result["warning"] = "远端已包含当前 HEAD，但 updates.md 没有对应的远端提交记录。"
    elif result["status"] == "mismatch":
        result["warning"] = "本地 HEAD 与远端分支提交不一致，请确认是否已推送正确分支。"
    return result


def append_push_verification(path: Path, payload: dict[str, object], work: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if "当前暂无更新记录。" in text:
        text = text.replace("当前暂无更新记录。", "", 1).rstrip()
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    commit = str(payload["remote_commit"])
    record = f"""
## {timestamp} · {work} · 远端推送核验

- 类型：verification
- 变更：核对分支 {payload['branch']} 的远端提交
- 决策：以 git ls-remote 返回的远端提交为准
- 依据：Git 远端 {payload['remote']} / 分支 {payload['branch']}
- 验证：远端 HEAD={commit}
- 本地提交：{payload['local_commit']}
- 远端推送：已验证；远端 HEAD={commit}
"""
    path.write_text(text.rstrip() + "\n" + record, encoding="utf-8", newline="\n")


def push_check(root: Path, as_json: bool, record: bool, work: str) -> int:
    payload = push_status(root)
    if record and payload["status"] == "up_to_date" and payload["remote_commit"]:
        path = root / HISTORY_RELATIVE
        if not path.is_file():
            raise RuntimeError(f"缺少更新历史：{path}；请先运行 project-lifecycle.ps1 init。")
        if payload["history_status"] != "recorded":
            append_push_verification(path, payload, work)
            payload = push_status(root)
            payload["recorded"] = True
        else:
            payload["recorded"] = False
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"远端核验：{payload['status']}")
        print(f"更新历史：{payload['history_status']}")
        if payload["remote"]:
            print(f"远端：{payload['remote']} / {payload['branch']}")
        if payload["local_commit"]:
            print(f"本地 HEAD：{payload['local_commit']}")
        if payload["remote_commit"]:
            print(f"远端 HEAD：{payload['remote_commit']}")
        if payload["warning"]:
            print(f"注意：{payload['warning']}")
    return 0 if payload["consistent"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--list", action="store_true", help="查看更新历史")
    parser.add_argument("--record", action="store_true", help="追加一条更新记录")
    parser.add_argument("--check", action="store_true", help="检查本地 Git 提交检查点")
    parser.add_argument("--push-check", action="store_true", help="查询远端提交并检查更新历史")
    parser.add_argument("--record-push", action="store_true", help="核验成功后追加远端验证记录")
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
        if args.push_check:
            if args.record:
                parser.error("--push-check 使用 --record-push，不要同时传 --record")
            return push_check(root, args.json, args.record_push, args.work)
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
