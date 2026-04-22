param(
    [string]$Action
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: .\two-lane-local-lab.ps1 <start|park|status> [--help]

Coordinate the local Windows lab pieces for lane-01 and lane-02.

Optional environment overrides:
  TUNNEL_SERVICE_SCRIPT
  CHROME_SERVICE_SCRIPT
"@
}

if ([string]::IsNullOrWhiteSpace($Action) -or $Action -eq "--help") {
    Show-Usage
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tunnelServiceScript = if ($env:TUNNEL_SERVICE_SCRIPT) { $env:TUNNEL_SERVICE_SCRIPT } else { Join-Path $scriptDir "local-tunnel-service.ps1" }
$chromeServiceScript = if ($env:CHROME_SERVICE_SCRIPT) { $env:CHROME_SERVICE_SCRIPT } else { Join-Path $scriptDir "local-chrome-service.ps1" }

function Invoke-JsonScript([string]$ScriptPath, [string]$RequestedAction) {
    if (-not (Test-Path $ScriptPath)) {
        return @{
            status = "missing"
            detail = $ScriptPath
        }
    }

    $output = powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath $RequestedAction
    if ($LASTEXITCODE -ne 0) {
        throw "Script failed: $ScriptPath $RequestedAction"
    }
    return $output | ConvertFrom-Json
}

function Write-AggregatedStatus {
    $tunnels = Invoke-JsonScript $tunnelServiceScript "status"
    $chrome = Invoke-JsonScript $chromeServiceScript "status"
    @{
        tunnels = $tunnels
        chrome = $chrome
    } | ConvertTo-Json -Depth 10
}

switch ($Action) {
    "start" {
        Invoke-JsonScript $tunnelServiceScript "start" | Out-Null
        Invoke-JsonScript $chromeServiceScript "start" | Out-Null
        Write-AggregatedStatus
    }
    "park" {
        Invoke-JsonScript $chromeServiceScript "park" | Out-Null
        Invoke-JsonScript $tunnelServiceScript "park" | Out-Null
        Write-AggregatedStatus
    }
    "status" {
        Write-AggregatedStatus
    }
    default {
        Show-Usage
        exit 1
    }
}
