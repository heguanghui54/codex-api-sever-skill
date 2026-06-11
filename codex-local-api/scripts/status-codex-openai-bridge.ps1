param(
    [string]$StateDir = $env:CODEX_BRIDGE_STATE_DIR
)

$ErrorActionPreference = "Stop"

if (-not $StateDir) {
    $StateDir = Join-Path $HOME ".codex-local-api"
}
$StateDir = [System.IO.Path]::GetFullPath($StateDir)
$PidFile = Join-Path $StateDir "codex_openai_bridge.pid"
$InfoFile = Join-Path $StateDir "codex_openai_bridge_info.json"
$EnvFile = Join-Path $StateDir "codex-openai-bridge.env"

if (-not (Test-Path $PidFile)) {
    Write-Output "Not running: no PID file at $PidFile"
    exit 1
}

$PidValue = (Get-Content $PidFile -Raw).Trim()
$Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
if (-not $Process) {
    Write-Output "Not running: stale PID $PidValue"
    exit 1
}

Write-Output "Running: pid=$PidValue"
if (Test-Path $InfoFile) {
    Get-Content $InfoFile -Raw
}
if (Test-Path $EnvFile) {
    Write-Output "Env file: $EnvFile"
    Get-Content $EnvFile
}
