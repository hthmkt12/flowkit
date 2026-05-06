param(
    [switch]$PrintOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"

$env:LIVE_ACTIONS_ENABLED = "false"
$env:DRY_RUN_DEFAULT = "true"
$env:APPROVAL_REQUIRED = "true"
$env:API_AUTH_ENABLED = "false"
$env:WS_AUTH_ENABLED = "false"

$command = "& `"$pythonPath`" -m agent.main"

Write-Output "FBKit safe mode environment:"
Write-Output "LIVE_ACTIONS_ENABLED=$env:LIVE_ACTIONS_ENABLED"
Write-Output "DRY_RUN_DEFAULT=$env:DRY_RUN_DEFAULT"
Write-Output "APPROVAL_REQUIRED=$env:APPROVAL_REQUIRED"
Write-Output "API_AUTH_ENABLED=$env:API_AUTH_ENABLED"
Write-Output "WS_AUTH_ENABLED=$env:WS_AUTH_ENABLED"
Write-Output "Command: $command"

if ($PrintOnly) {
    return
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtualenv not found at $pythonPath"
}

Set-Location -LiteralPath $repoRoot
& $pythonPath -m agent.main
