param(
    [string]$StateDir = $env:CODEX_BRIDGE_STATE_DIR
)

$ErrorActionPreference = "Stop"

if (-not $StateDir) {
    $StateDir = Join-Path $HOME ".codex-local-api"
}
$PidFile = Join-Path ([System.IO.Path]::GetFullPath($StateDir)) "codex_native_app_server.pid"

if (-not (Test-Path $PidFile)) {
    Write-Output "Not running: no PID file at $PidFile"
    exit 0
}

$PidValue = (Get-Content $PidFile -Raw).Trim()
$Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
if ($Process) {
    Stop-Process -Id $PidValue -Force
    Write-Output "Stopped Codex native app-server pid=$PidValue"
} else {
    Write-Output "Removed stale PID file for pid=$PidValue"
}
Remove-Item -LiteralPath $PidFile -Force
