param(
    [switch]$IncludeChrome
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFiles = @(
    ".fbkit-agent-smoke.pid",
    ".fbkit-chrome-smoke.pid"
)

function Stop-ProcessIfRunning {
    param(
        [int]$ProcessId,
        [string]$Label
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Output "$Label process $ProcessId is not running."
        return $false
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    $stillRunning = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($stillRunning) {
        Write-Output "Could not stop $Label process $ProcessId."
        return $false
    }

    Write-Output "Stopped $Label process $ProcessId."
    return $true
}

function Get-ProcessDetails {
    param([int]$ProcessId)
    return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Test-FBKitAgentProcess {
    param([int]$ProcessId)

    $details = Get-ProcessDetails -ProcessId $ProcessId
    if (-not $details) {
        return $false
    }

    $repoPrefix = $repoRoot.ToLowerInvariant()
    $executablePath = [string]$details.ExecutablePath
    $commandLine = [string]$details.CommandLine
    $normalizedExecutable = $executablePath.ToLowerInvariant()
    $normalizedCommand = $commandLine.ToLowerInvariant()

    $isRepoProcess = $normalizedExecutable.StartsWith($repoPrefix) -or $normalizedCommand.Contains($repoPrefix)
    $isAgentCommand = $normalizedCommand.Contains("agent.main")

    return $isRepoProcess -and $isAgentCommand
}

function Test-SmokeChromeProcess {
    param([int]$ProcessId)

    $details = Get-ProcessDetails -ProcessId $ProcessId
    if (-not $details) {
        return $false
    }

    $commandLine = ([string]$details.CommandLine).ToLowerInvariant()
    $runtimeProfile = (Join-Path $repoRoot "runtime\chrome-fbkit-smoke").ToLowerInvariant()

    return $commandLine.Contains("chrome") -and $commandLine.Contains($runtimeProfile)
}

Set-Location -LiteralPath $repoRoot

foreach ($pidFile in $pidFiles) {
    if (-not (Test-Path -LiteralPath $pidFile)) {
        continue
    }

    $pidValue = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidValue -match '^\d+$') {
        $label = if ($pidFile -like '*chrome*') { "Chrome smoke" } else { "FBKit smoke" }
        if ($pidFile -like '*chrome*' -and -not $IncludeChrome) {
            Write-Output "Keeping Chrome smoke process $pidValue. Pass -IncludeChrome to stop it."
            continue
        } elseif ($pidFile -like '*chrome*' -and -not (Test-SmokeChromeProcess -ProcessId ([int]$pidValue))) {
            Write-Output "Skipping non-smoke Chrome process $pidValue from $pidFile."
        } elseif ($pidFile -like '*agent*' -and -not (Test-FBKitAgentProcess -ProcessId ([int]$pidValue))) {
            Write-Output "Skipping non-FBKit process $pidValue from $pidFile."
        } else {
            Stop-ProcessIfRunning -ProcessId ([int]$pidValue) -Label $label
        }
    }

    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Output "Removed $pidFile."
}

$listenerPorts = @(8100, 9222)
foreach ($port in $listenerPorts) {
    $connections = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -gt 0) {
            if (Test-FBKitAgentProcess -ProcessId $connection.OwningProcess) {
                Stop-ProcessIfRunning -ProcessId $connection.OwningProcess -Label "FBKit listener on port $port"
            } else {
                Write-Output "Skipping non-FBKit listener $($connection.OwningProcess) on port $port."
            }
        }
    }
}

Write-Output "FBKit smoke cleanup complete."
