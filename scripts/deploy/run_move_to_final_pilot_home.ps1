param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"
$DatasetRoot = Join-Path $RepoRoot "data\so101-left-final-pilot"

Write-Host ""
Write-Host "Move follower to final-pilot home pose."
Write-Host "Keep one hand near power/stop. Clear the workspace."
Write-Host ""
Read-Host "Press Enter to start"

& $Python (Join-Path $PSScriptRoot "move_to_final_pilot_home.py") `
    --config-path "$ConfigPath" `
    --dataset-root "$DatasetRoot" `
    --fps 10 `
    --per-step-deg 3 `
    --tolerance 2 `
    --timeout-s 25 `
    --motor-retries 5
