param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8787,
    [string]$ApiKey = $env:CODEX_BRIDGE_API_KEY,
    [string]$Cwd = (Get-Location).Path,
    [string]$Python = $env:PYTHON,
    [string]$Codex = $env:CODEX_BIN,
    [int]$Timeout = 600,
    [string]$StateDir = $env:CODEX_BRIDGE_STATE_DIR
)

$ErrorActionPreference = "Stop"

if (-not $StateDir) {
    $StateDir = Join-Path $HOME ".codex-local-api"
}
$StateDir = [System.IO.Path]::GetFullPath($StateDir)
$LogsDir = Join-Path $StateDir "logs"
New-Item -ItemType Directory -Force -Path $StateDir, $LogsDir | Out-Null

$SkillRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $SkillRoot "scripts\codex_openai_bridge.py"
$PidFile = Join-Path $StateDir "codex_openai_bridge.pid"
$InfoFile = Join-Path $StateDir "codex_openai_bridge_info.json"
$EnvFile = Join-Path $StateDir "codex-openai-bridge.env"
$Log = Join-Path $LogsDir "codex_openai_bridge.log"
$ErrLog = Join-Path $LogsDir "codex_openai_bridge.err.log"

if (-not $Python) {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) { $Python = $PythonCmd.Source }
}
if (-not $Python) {
    throw "Python was not found. Install Python 3.10+ or pass -Python C:\Path\to\python.exe"
}
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

if (-not $ApiKey -and (Test-Path $EnvFile)) {
    $Existing = Get-Content $EnvFile | Where-Object { $_ -match '^CODEX_BRIDGE_API_KEY=' } | Select-Object -First 1
    if ($Existing) { $ApiKey = $Existing.Split("=", 2)[1] }
}
if (-not $ApiKey) {
    $ApiKey = "sk-codex-local-" + ([guid]::NewGuid().ToString("N"))
}

if (Test-Path $PidFile) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid -and (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue)) {
        Write-Output "Already running: http://${HostName}:$Port/v1 pid=$ExistingPid"
        Write-Output "API key: $ApiKey"
        exit 0
    }
}

$env:CODEX_BRIDGE_STATE_DIR = $StateDir
$env:CODEX_BIN = $Codex

$Args = @(
    $Script,
    "--host", $HostName,
    "--port", "$Port",
    "--api-key", $ApiKey,
    "--codex", $Codex,
    "--cwd", $Cwd,
    "--timeout", "$Timeout",
    "--log", $Log,
    "--err-log", $ErrLog
)
$Process = Start-Process -FilePath $Python -ArgumentList $Args -WorkingDirectory $Cwd -WindowStyle Hidden -PassThru
Set-Content -Path $PidFile -Value $Process.Id -Encoding ASCII

$BaseUrl = "http://${HostName}:$Port/v1"
$Info = @{
    base_url = $BaseUrl
    api_key = $ApiKey
    pid = $Process.Id
    cwd = $Cwd
    codex = $Codex
    python = $Python
    state_dir = $StateDir
    log = $Log
    error_log = $ErrLog
} | ConvertTo-Json
Set-Content -Path $InfoFile -Value $Info -Encoding UTF8

@(
    "OPENAI_BASE_URL=$BaseUrl",
    "OPENAI_API_KEY=$ApiKey",
    "OPENAI_MODEL=codex",
    "CODEX_BRIDGE_BASE_URL=$BaseUrl",
    "CODEX_BRIDGE_API_KEY=$ApiKey",
    "CODEX_BRIDGE_STATE_DIR=$StateDir"
) | Set-Content -Path $EnvFile -Encoding ASCII

Write-Output "Started: $BaseUrl"
Write-Output "API key: $ApiKey"
Write-Output "PID: $($Process.Id)"
Write-Output "Env file: $EnvFile"
