param(
    [string]$Action
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: .\local-tunnel-service.ps1 <start|park|status> [--help]

Manage the local Windows SSH tunnels for lane-01 and lane-02.

Optional environment overrides:
  SSH_EXE
  SSH_HOST
  LANE_01_PORTS
  LANE_02_PORTS
"@
}

if ([string]::IsNullOrWhiteSpace($Action) -or $Action -eq "--help") {
    Show-Usage
    exit 0
}

$sshExe = if ($env:SSH_EXE) { $env:SSH_EXE } else { "ssh" }
$sshHost = if ($env:SSH_HOST) { $env:SSH_HOST } else { "hth2-box" }
$lane01Ports = if ($env:LANE_01_PORTS) { $env:LANE_01_PORTS } else { "8100:127.0.0.1:8100,9222:127.0.0.1:9222" }
$lane02Ports = if ($env:LANE_02_PORTS) { $env:LANE_02_PORTS } else { "8110:127.0.0.1:8110,9232:127.0.0.1:9232,18182:127.0.0.1:18182" }

function Get-LaneSpec([string]$Label, [string]$PortsValue) {
    $forwards = @($PortsValue.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($forwards.Count -eq 0) {
        throw "No forwards configured for $Label"
    }
    return @{
        label = $Label
        forwards = $forwards
        primary_forward = $forwards[0]
    }
}

function Get-ProcessName([string]$Executable) {
    $name = [System.IO.Path]::GetFileName($Executable)
    if (-not $name) {
        return "ssh.exe"
    }
    if ($name -notmatch "\.exe$") {
        return "$name.exe"
    }
    return $name
}

function Get-LaneTunnelProcesses($Spec) {
    $processName = Get-ProcessName $sshExe
    $needle = "-L $($Spec.primary_forward)"
    return @(
        Get-CimInstance Win32_Process -Filter "name = '$processName'" -ErrorAction SilentlyContinue |
        Where-Object {
            $cmd = $_.CommandLine
            $cmd -and $cmd.Contains($needle) -and $cmd.Contains($sshHost)
        }
    )
}

function Get-LaneTunnelStatus($Spec) {
    $processes = Get-LaneTunnelProcesses $Spec
    return @{
        running = $processes.Count -gt 0
        process_ids = @($processes | Select-Object -ExpandProperty ProcessId)
        forwards = $Spec.forwards
        host = $sshHost
    }
}

function Start-LaneTunnel($Spec) {
    if ((Get-LaneTunnelProcesses $Spec).Count -gt 0) {
        return
    }

    $arguments = @("-N")
    foreach ($forward in $Spec.forwards) {
        $arguments += "-L"
        $arguments += $forward
    }
    $arguments += $sshHost

    Start-Process -FilePath $sshExe -ArgumentList $arguments | Out-Null
}

function Stop-LaneTunnel($Spec) {
    $processes = Get-LaneTunnelProcesses $Spec
    foreach ($process in $processes) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$lane01 = Get-LaneSpec "lane-01" $lane01Ports
$lane02 = Get-LaneSpec "lane-02" $lane02Ports

switch ($Action) {
    "start" {
        Start-LaneTunnel $lane01
        Start-LaneTunnel $lane02
        Start-Sleep -Seconds 2
        @{
            lane_01 = Get-LaneTunnelStatus $lane01
            lane_02 = Get-LaneTunnelStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    "park" {
        Stop-LaneTunnel $lane01
        Stop-LaneTunnel $lane02
        @{
            lane_01 = Get-LaneTunnelStatus $lane01
            lane_02 = Get-LaneTunnelStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    "status" {
        @{
            lane_01 = Get-LaneTunnelStatus $lane01
            lane_02 = Get-LaneTunnelStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    default {
        Show-Usage
        exit 1
    }
}
