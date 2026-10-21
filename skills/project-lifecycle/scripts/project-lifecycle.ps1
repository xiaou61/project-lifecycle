[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

# 命令映射只在 project-lifecycle.py 维护一份；这里只负责找到 Python 并转发。
$ErrorActionPreference = "Stop"
$entry = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "project-lifecycle.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -X utf8 $entry $Command @CommandArgs
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -X utf8 $entry $Command @CommandArgs
}
else {
    throw "未找到 Python 运行时。请让 Agent 使用已安装 Skill 的命令入口，或由维护者配置 Python；用户不需要直接运行 Python。"
}

exit $LASTEXITCODE
