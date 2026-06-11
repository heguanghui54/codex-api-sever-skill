param(
    [int]$Port = 8791,
    [string]$Cwd = (Get-Location).Path,
    [string]$Codex = $env:CODEX_BIN,
    [string]$StateDir = $env:CODEX_BRIDGE_STATE_DIR
)

$ErrorActionPreference = "Stop"

if (-not $StateDir) {
    $StateDir = Join-Path $HOME ".codex-local-api"
}
$StateDir = [System.IO.Path]::GetFullPath($StateDir)
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if (-not $Codex) {
    $CodexCmd = Get-Command codex -ErrorAction SilentlyContinue
    if ($CodexCmd) { $Codex = $CodexCmd.Source }
}
if (-not $Codex) {
    $Candidate = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\bin\codex.exe"
    if (Test-Path $Candidate) { $Codex = $Candidate }
}
if (-not $Codex) {
    throw "Codex CLI was not found. Install/sign in to Codex CLI or pass -Codex C:\Path\to\codex.exe"
}

$PidFile = Join-Path $StateDir "codex_native_app_server.pid"
$InfoFile = Join-Path $StateDir "codex_native_app_server_info.json"
$Url = "ws://127.0.0.1:$Port"

if (Test-Path $PidFile) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid -and (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue)) {
        Write-Output "Already running: $Url pid=$ExistingPid"
        exit 0
    }
}

$Process = Start-Process -FilePath $Codex -ArgumentList @("app-server", "--listen", $Url) -WorkingDirectory $Cwd -WindowStyle Hidden -PassThru
Set-Content -Path $PidFile -Value $Process.Id -Encoding ASCII

$Info = @{
    websocket_url = $Url
    pid = $Process.Id
    cwd = $Cwd
    codex = $Codex
    state_dir = $StateDir
} | ConvertTo-Json
Set-Content -Path $InfoFile -Value $Info -Encoding UTF8

Write-Output "Started Codex native app-server: $Url"
Write-Output "PID: $($Process.Id)"
