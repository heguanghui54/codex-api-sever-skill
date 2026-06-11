param(
    [string]$CodexHome = $env:CODEX_HOME
)

$ErrorActionPreference = "Stop"

if (-not $CodexHome) {
    $CodexHome = Join-Path $HOME ".codex"
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $RepoRoot "codex-local-api"
$DestRoot = Join-Path $CodexHome "skills"
$Dest = Join-Path $DestRoot "codex-local-api"

if (-not (Test-Path $Source)) {
    throw "Skill folder not found: $Source"
}

New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
if (Test-Path $Dest) {
    Remove-Item -LiteralPath $Dest -Recurse -Force
}
Copy-Item -LiteralPath $Source -Destination $Dest -Recurse

Write-Output "Installed skill to: $Dest"
Write-Output "Restart Codex if the skill list does not refresh automatically."
