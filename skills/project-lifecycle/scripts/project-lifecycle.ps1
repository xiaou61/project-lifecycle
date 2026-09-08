[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("init", "status", "resume", "validate", "history")]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonPrefix = @("-3", "-X", "utf8")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
    $pythonPrefix = @("-X", "utf8")
}
else {
    throw "未找到 Python 运行时。请让 Agent 使用已安装 Skill 的命令入口，或由维护者配置 Python；用户不需要直接运行 Python。"
}

$scriptName = switch ($Command) {
    "init" { "init_project.py" }
    "status" { "project_status.py" }
    "resume" { "project_status.py" }
    "validate" { "project_validate.py" }
    "history" { "generate_core_history.py" }
}

$forwardedArgs = @($CommandArgs)
if ($Command -eq "resume" -and $forwardedArgs -notcontains "--resume") {
    $forwardedArgs += "--resume"
}
if ($Command -eq "validate" -and $forwardedArgs -notcontains "--strict") {
    $forwardedArgs += "--strict"
}

& $pythonCommand @pythonPrefix (Join-Path $scriptDir $scriptName) @forwardedArgs
exit $LASTEXITCODE
