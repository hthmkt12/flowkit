param(
    [string]$Action
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: .\local-chrome-service.ps1 <start|park|status> [--help]

Manage the local Windows Chrome profiles for lane-01 and lane-02.

Optional environment overrides:
  CHROME_EXE
  LANE_01_PROFILE_DIR
  LANE_01_EXTENSION_DIR
  LANE_01_URLS
  LANE_02_PROFILE_DIR
  LANE_02_EXTENSION_DIR
  LANE_02_URLS
"@
}

if ([string]::IsNullOrWhiteSpace($Action) -or $Action -eq "--help") {
    Show-Usage
    exit 0
}

$chromeExe = if ($env:CHROME_EXE) { $env:CHROME_EXE } else { "C:\Program Files\Google\Chrome\Application\chrome.exe" }
$lane01ProfileDir = if ($env:LANE_01_PROFILE_DIR) { $env:LANE_01_PROFILE_DIR } else { "C:\temp\flowkit-real-chrome\UserData" }
$lane01ExtensionDir = if ($env:LANE_01_EXTENSION_DIR) { $env:LANE_01_EXTENSION_DIR } else { "C:\temp\flowkit-extension-unpacked" }
$lane01Urls = if ($env:LANE_01_URLS) { $env:LANE_01_URLS } else { "https://accounts.google.com/,https://labs.google/fx/tools/flow,chrome://extensions" }
$lane02ProfileDir = if ($env:LANE_02_PROFILE_DIR) { $env:LANE_02_PROFILE_DIR } else { "C:\temp\flowkit-real-chrome-lane-02\UserData" }
$lane02ExtensionDir = if ($env:LANE_02_EXTENSION_DIR) { $env:LANE_02_EXTENSION_DIR } else { "C:\temp\flowkit-extension-unpacked-lane-02" }
$lane02Urls = if ($env:LANE_02_URLS) { $env:LANE_02_URLS } else { "chrome://extensions,https://labs.google/fx/tools/flow" }

function Get-LaneSpec([string]$Label, [string]$ProfileDir, [string]$ExtensionDir, [string]$UrlsValue) {
    return @{
        label = $Label
        profile_dir = $ProfileDir
        extension_dir = $ExtensionDir
        urls = @($UrlsValue.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
}

function Get-LaneChromeProcesses($Spec) {
    return @(
        Get-CimInstance Win32_Process -Filter "name = 'chrome.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $cmd = $_.CommandLine
            $cmd -and $cmd.Contains($Spec.profile_dir)
        }
    )
}

function Get-LaneChromeStatus($Spec) {
    $processes = Get-LaneChromeProcesses $Spec
    return @{
        running = $processes.Count -gt 0
        process_ids = @($processes | Select-Object -ExpandProperty ProcessId)
        profile_dir = $Spec.profile_dir
        extension_dir = $Spec.extension_dir
    }
}

function Start-LaneChrome($Spec) {
    if ((Get-LaneChromeProcesses $Spec).Count -gt 0) {
        return
    }

    $arguments = @(
        "--user-data-dir=$($Spec.profile_dir)",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=DisableLoadExtensionCommandLineSwitch,DisableDisableExtensionsExceptCommandLineSwitch",
        "--disable-extensions-except=$($Spec.extension_dir)",
        "--load-extension=$($Spec.extension_dir)"
    ) + $Spec.urls

    Start-Process -FilePath $chromeExe -ArgumentList $arguments | Out-Null
}

function Stop-LaneChrome($Spec) {
    $processes = Get-LaneChromeProcesses $Spec
    foreach ($process in $processes) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$lane01 = Get-LaneSpec "lane-01" $lane01ProfileDir $lane01ExtensionDir $lane01Urls
$lane02 = Get-LaneSpec "lane-02" $lane02ProfileDir $lane02ExtensionDir $lane02Urls

switch ($Action) {
    "start" {
        Start-LaneChrome $lane01
        Start-LaneChrome $lane02
        Start-Sleep -Seconds 2
        @{
            lane_01 = Get-LaneChromeStatus $lane01
            lane_02 = Get-LaneChromeStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    "park" {
        Stop-LaneChrome $lane01
        Stop-LaneChrome $lane02
        @{
            lane_01 = Get-LaneChromeStatus $lane01
            lane_02 = Get-LaneChromeStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    "status" {
        @{
            lane_01 = Get-LaneChromeStatus $lane01
            lane_02 = Get-LaneChromeStatus $lane02
        } | ConvertTo-Json -Depth 8
    }
    default {
        Show-Usage
        exit 1
    }
}
