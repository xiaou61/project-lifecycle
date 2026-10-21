#!/usr/bin/env python3
"""跨平台命令入口：把子命令转发到对应的实现脚本。

Windows 用 project-lifecycle.ps1，POSIX 用 project-lifecycle.sh，两者都转发到这里，
命令映射只维护这一份。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

COMMANDS = {
    "init": ("init_project.py", []),
    "status": ("project_status.py", []),
    "brief": ("project_status.py", ["--brief"]),
    "resume": ("project_status.py", ["--resume"]),
    "validate": ("project_validate.py", []),
    "history": ("generate_core_history.py", []),
    "updates": ("update_history.py", ["--list"]),
    "record": ("update_history.py", ["--record"]),
    "approve": ("update_history.py", ["--approve"]),
    "archive": ("update_history.py", ["--archive"]),
    "checkpoint": ("update_history.py", ["--check"]),
    "push-check": ("update_history.py", ["--push-check"]),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("用法: project-lifecycle.py <命令> [参数...]")
        print("命令: " + ", ".join(COMMANDS))
        return 0 if len(argv) > 1 else 2
    if argv[1] not in COMMANDS:
        print(f"未知命令：{argv[1]}；可用命令：{', '.join(COMMANDS)}", file=sys.stderr)
        return 2
    name, implicit = COMMANDS[argv[1]]
    args = argv[2:]
    args += [flag for flag in implicit if flag not in args]
    target = Path(__file__).resolve().parent / name
    return subprocess.call([sys.executable, "-X", "utf8", str(target), *args])


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print(f"需要 Python 3.9 或更高版本；当前为 {sys.version.split()[0]}。", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv))
