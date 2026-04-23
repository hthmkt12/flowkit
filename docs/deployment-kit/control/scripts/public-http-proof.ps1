param(
    [string]$Action
)

$ErrorActionPreference = "Stop"

function New-DefaultSourceTitle([string]$BaseTitle) {
    return "{0} {1}" -f $BaseTitle, (Get-Date -Format "yyyy-MM-dd HH-mm-ss")
}

function Show-Usage {
    @"
Usage: .\public-http-proof.ps1 <run|status> [--help]

Run the same-VM public HTTP proof end-to-end:
- start local Windows lab
- start remote VM lab
- execute remote public-http-fresh-smoke helper
- park both sides again

Optional environment overrides:
  LOCAL_LAB_SCRIPT
  SSH_EXE
  REMOTE_HOST
  REMOTE_CONTROL_ROOT
  REMOTE_LAB_SCRIPT
  REMOTE_FRESH_SMOKE_SCRIPT
  REMOTE_CONTROL_PROFILE
  REMOTE_LANE_ENV
  SOURCE_TITLE
  SOURCE_BRIEF
  TARGET_DURATION_SECONDS
  CHAPTER_COUNT
  MATERIAL_ID
  START_DELAY_SECONDS
  WAIT_FOR_READY=1
  WAIT_TIMEOUT_SECONDS=180
  POLL_INTERVAL_SECONDS=5
"@
}

if ($Action -eq "--help" -or $args -contains "--help") {
    Show-Usage
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Action)) {
    $Action = "run"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$localLabScript = if ($env:LOCAL_LAB_SCRIPT) { $env:LOCAL_LAB_SCRIPT } else { Join-Path $scriptDir "two-lane-local-lab.ps1" }
$sshExe = if ($env:SSH_EXE) { $env:SSH_EXE } else { "ssh" }
$remoteHost = if ($env:REMOTE_HOST) { $env:REMOTE_HOST } else { "hth2-box" }
$remoteControlRoot = if ($env:REMOTE_CONTROL_ROOT) { $env:REMOTE_CONTROL_ROOT } else { "/home/hth2/flowkit-control-demo/control" }
$remoteLabScript = if ($env:REMOTE_LAB_SCRIPT) { $env:REMOTE_LAB_SCRIPT } else { "./scripts/two-lane-lab-service.sh" }
$remoteFreshSmokeScript = if ($env:REMOTE_FRESH_SMOKE_SCRIPT) { $env:REMOTE_FRESH_SMOKE_SCRIPT } else { "./scripts/public-http-fresh-smoke.sh" }
$remoteControlProfile = if ($env:REMOTE_CONTROL_PROFILE) { $env:REMOTE_CONTROL_PROFILE } else { "/home/hth2/flowkit-control-demo/control/host-demo.env" }
$remoteLaneEnv = if ($env:REMOTE_LANE_ENV) { $env:REMOTE_LANE_ENV } else { "/home/hth2/flowkit-worker-demo-lane-02/env/lane.env" }
$sourceTitle = if ([string]::IsNullOrWhiteSpace($env:SOURCE_TITLE)) { New-DefaultSourceTitle "Public HTTP Wrapper Smoke" } else { $env:SOURCE_TITLE }
$sourceBrief = if ($env:SOURCE_BRIEF) { $env:SOURCE_BRIEF } else { "One-command wrapper proof for public HTTP artifact URLs." }
$targetDurationSeconds = if ($env:TARGET_DURATION_SECONDS) { [int]$env:TARGET_DURATION_SECONDS } else { 8 }
$chapterCount = if ($env:CHAPTER_COUNT) { [int]$env:CHAPTER_COUNT } else { 1 }
$materialId = if ($env:MATERIAL_ID) { $env:MATERIAL_ID } else { "realistic" }
$startDelaySeconds = if ($env:START_DELAY_SECONDS) { [int]$env:START_DELAY_SECONDS } else { 10 }
$waitForReady = if ($env:WAIT_FOR_READY) { $env:WAIT_FOR_READY } else { "1" }
$waitTimeoutSeconds = if ($env:WAIT_TIMEOUT_SECONDS) { [int]$env:WAIT_TIMEOUT_SECONDS } else { 180 }
$pollIntervalSeconds = if ($env:POLL_INTERVAL_SECONDS) { [int]$env:POLL_INTERVAL_SECONDS } else { 5 }

function Convert-ToShellLiteral([string]$Value) {
    return "'" + ($Value -replace "'", "'\''") + "'"
}

function Invoke-JsonPowerShell([string]$ScriptPath, [string]$RequestedAction) {
    $output = powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath $RequestedAction
    if ($LASTEXITCODE -ne 0) {
        throw "Script failed: $ScriptPath $RequestedAction"
    }
    return $output | ConvertFrom-Json
}

function Invoke-RemoteRaw([string]$RemoteCommand) {
    $output = & $sshExe $remoteHost $RemoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed on ${remoteHost}: $RemoteCommand"
    }
    return $output
}

function Invoke-RemoteJson([string]$RemoteCommand) {
    $output = Invoke-RemoteRaw $RemoteCommand
    return $output | ConvertFrom-Json
}

function New-RemoteBasePrefix {
    return "cd $(Convert-ToShellLiteral $remoteControlRoot) && "
}

function New-RemoteLabCommand([string]$RequestedAction) {
    return "$(New-RemoteBasePrefix)$remoteLabScript $RequestedAction"
}

function New-RemoteFreshSmokeCommand {
    $parts = @(
        "cd $(Convert-ToShellLiteral $remoteControlRoot)",
        "chmod +x $(Convert-ToShellLiteral $remoteFreshSmokeScript)",
        "set -a",
        ". $(Convert-ToShellLiteral $remoteLaneEnv)",
        "set +a",
        "CONTROL_PROFILE_FILE=$(Convert-ToShellLiteral $remoteControlProfile)",
        "SOURCE_TITLE=$(Convert-ToShellLiteral $sourceTitle)",
        "SOURCE_BRIEF=$(Convert-ToShellLiteral $sourceBrief)",
        "TARGET_DURATION_SECONDS=$(Convert-ToShellLiteral $targetDurationSeconds)",
        "CHAPTER_COUNT=$(Convert-ToShellLiteral $chapterCount)",
        "MATERIAL_ID=$(Convert-ToShellLiteral $materialId)",
        $remoteFreshSmokeScript
    )
    return ($parts -join " && ")
}

function Write-StatusPayload {
    $localStatus = Invoke-JsonPowerShell $localLabScript "status"
    $remoteStatus = Invoke-RemoteJson (New-RemoteLabCommand "status")
    @{
        local = $localStatus
        remote = $remoteStatus
    } | ConvertTo-Json -Depth 12
}

function Test-RemoteLabReady([object]$RemoteStatus) {
    if (-not $RemoteStatus) {
        return $false
    }
    if (-not $RemoteStatus.control.control_api_running) {
        return $false
    }
    if (-not $RemoteStatus.control.scheduler_running) {
        return $false
    }
    if (-not $RemoteStatus.lane_01.ready.ok) {
        return $false
    }
    if (-not $RemoteStatus.lane_02.ready.ok) {
        return $false
    }
    return $true
}

function Wait-ForRemoteLabReady {
    $deadline = (Get-Date).AddSeconds($waitTimeoutSeconds)
    do {
        $status = Invoke-RemoteJson (New-RemoteLabCommand "status")
        if (Test-RemoteLabReady $status) {
            return $status
        }
        Start-Sleep -Seconds $pollIntervalSeconds
    } while ((Get-Date) -lt $deadline)
    throw "Remote lab did not become ready within $waitTimeoutSeconds seconds"
}

switch ($Action) {
    "status" {
        Write-StatusPayload
    }
    "run" {
        $proofResult = $null
        try {
            Invoke-JsonPowerShell $localLabScript "start" | Out-Null
            Invoke-RemoteJson (New-RemoteLabCommand "start") | Out-Null
            Start-Sleep -Seconds $startDelaySeconds
            if ($waitForReady -eq "1") {
                Wait-ForRemoteLabReady | Out-Null
            }
            $proofResult = Invoke-RemoteJson (New-RemoteFreshSmokeCommand)
        }
        finally {
            try {
                Invoke-JsonPowerShell $localLabScript "park" | Out-Null
            }
            catch {
                Write-Warning "Local park failed: $($_.Exception.Message)"
            }
            try {
                Invoke-RemoteJson (New-RemoteLabCommand "park") | Out-Null
            }
            catch {
                Write-Warning "Remote park failed: $($_.Exception.Message)"
            }
        }

        if ($null -eq $proofResult) {
            throw "Proof did not produce a result"
        }

        $proofResult | ConvertTo-Json -Depth 12
    }
    default {
        Show-Usage
        exit 1
    }
}
