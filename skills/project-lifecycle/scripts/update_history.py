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
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"
# 只有已经存在阶段门槛的工件需要签署；lite 短路径和 testing/plan.md 不签。
APPROVAL_ARTIFACTS = {
    "requirements": Path("requirements.md"),
    "proposal": Path("proposal.md"),
    "design": Path("design.md"),
    "tasks": Path("tasks.md"),
    "test-report": Path("testing/report.md"),
}


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


def append_history_entry(
    path: Path,
    *,
    work: str,
    title: str,
    entry_type: str,
    change: str,
    decision: str,
    basis: str,
    verification: str,
    local_commit: str = "待用户授权/未提交",
    remote_push: str = "未执行",
) -> None:
    """追加一条记录；时间戳一律由本入口盖，不接受调用方传入。"""
    text = path.read_text(encoding="utf-8-sig")
    if "当前暂无更新记录。" in text:
        text = text.replace("当前暂无更新记录。", "", 1).rstrip()
    timestamp = datetime.now().astimezone().strftime(TIMESTAMP_FORMAT)
    record = f"""
## {timestamp} · {work} · {title}

- 类型：{entry_type}
- 变更：{change}
- 决策：{decision}
- 依据：{basis}
- 验证：{verification}
- 本地提交：{local_commit}
- 远端推送：{remote_push}
"""
    path.write_bytes((text.rstrip() + "\n" + record).encode("utf-8"))


def append_record(args: argparse.Namespace, path: Path) -> int:
    append_history_entry(
        path,
        work=args.work,
        title=args.title,
        entry_type=args.type,
        change=args.change,
        decision=args.decision,
        basis=args.basis,
        verification=args.verification,
        local_commit=args.local_commit,
        remote_push=args.remote_push,
    )
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
        "message": "存在未提交改动，需要形成本地检查点。" if dirty else "工作区干净，当前没有待提交改动。",
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
    commit = str(payload["remote_commit"])
    append_history_entry(
        path,
        work=work,
        title="远端推送核验",
        entry_type="verification",
        change=f"核对分支 {payload['branch']} 的远端提交",
        decision="以 git ls-remote 返回的远端提交为准",
        basis=f"Git 远端 {payload['remote']} / 分支 {payload['branch']}",
        verification=f"远端 HEAD={commit}",
        local_commit=str(payload["local_commit"]),
        remote_push=f"已验证；远端 HEAD={commit}",
    )


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

    `--artifact all` 一次签完工作项里已存在的阶段工件，并只追加一条 decision 记录。
    逐件签署会把更新历史淹成签名噪音，而"用户一次确认整版"本来就是一个事实。
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

    history = root / HISTORY_RELATIVE
    if not history.is_file():
        raise RuntimeError(f"缺少更新历史：{history}；请先运行 project-lifecycle.ps1 init。")
    accepted = args.artifact == "test-report"
    listing = "、".join(signed)
    append_history_entry(
        history,
        work=str(args.work).upper(),
        title=("登记业务验收 " if accepted else "签署 ") + listing,
        entry_type="decision",
        change=(
            f"登记业务验收：{listing}" if accepted else f"{listing} 由 {args.by} 签署为 approved"
        ),
        decision=f"审批人 {args.by}" + (f"（{role}）" if role else "") + "；签署字段由命令入口盖章，不由模型写入",
        basis=listing,
        verification=(
            f"回读 frontmatter：accepted_by={args.by}"
            if accepted
            else f"回读 frontmatter：approved_by={args.by}，{len(signed)} 个工件同批签署"
        ),
    )
    payload = {
        "project_root": str(root),
        "work_id": str(args.work).upper(),
        "artifact": args.artifact,
        "paths": signed,
        "signed_by": args.by,
        "role": role or None,
        "signed_at": timestamp,
        "history": str(history),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for relative in signed:
            print(f"已签署：{relative}")
        print(f"审批人：{args.by}" + (f"（{role}）" if role else ""))
        print(f"时间：{timestamp}")
        print(f"更新历史：{history}")
    return 0


def archive_completed(args: argparse.Namespace, root: Path) -> int:
    """把已完成的工作项移进 changes/archive/YYYY-MM-DD-<名称>。

    只移动目录、不改文件内容；旧路径引用由 validate 报告，updates.md 作为
    追加式时间线豁免。
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
            print("下一步：运行 validate 检查指向旧路径的引用；updates.md 不需要改。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="项目内任意路径")
    parser.add_argument("--list", action="store_true", help="查看更新历史")
    parser.add_argument("--record", action="store_true", help="追加一条更新记录")
    parser.add_argument("--check", action="store_true", help="检查本地 Git 提交检查点")
    parser.add_argument("--push-check", action="store_true", help="查询远端提交并检查更新历史")
    parser.add_argument("--record-push", action="store_true", help="核验成功后追加远端验证记录")
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
    parser.add_argument("--role", help="审批人角色，可选")
    args = parser.parse_args()
    try:
        root = project_status.locate_project(args.target)
        if args.check:
            return git_checkpoint(root, args.json)
        if args.approve:
            missing = [name for name in ("work", "artifact") if not getattr(args, name)]
            if missing:
                parser.error("--approve 缺少：" + ", ".join("--" + name for name in missing))
            if args.work == "maintenance":
                parser.error("--approve 必须指定真实的 --work 编号，不能使用默认的 maintenance")
            return approve(args, root)
        if args.archive:
            return archive_completed(args, root)
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
