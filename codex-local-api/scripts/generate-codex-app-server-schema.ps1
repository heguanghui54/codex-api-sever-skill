param(
    [string]$OutDir = (Join-Path (Join-Path $HOME ".codex-local-api") "schemas"),
    [string]$Codex = $env:CODEX_BIN
)

$ErrorActionPreference = "Stop"

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

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
& $Codex app-server generate-json-schema --out $OutDir
Write-Output "Schemas written to: $OutDir"
