#!/bin/sh
# 与 project-lifecycle.ps1 等价的 POSIX 入口；命令映射在 project-lifecycle.py。
dir=$(cd "$(dirname "$0")" && pwd)
# Windows 上的 python3 常是应用商店占位程序：能查到但一跑就退出，所以要试跑再选。
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "" >/dev/null 2>&1; then
        exec "$candidate" -X utf8 "$dir/project-lifecycle.py" "$@"
    fi
done
echo "未找到可用的 Python 3.9+ 运行时；请让 Agent 使用已安装 Skill 的命令入口。" >&2
exit 2
