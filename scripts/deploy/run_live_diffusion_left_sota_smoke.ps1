param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$PolicyPath = Join-Path $RepoRoot "models\diffusion-left-sota"
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"

if (-not (Test-Path (Join-Path $PolicyPath "model.safetensors"))) {
    Write-Host "Policy is missing. Downloading diffusion-left-sota first..."
    & $Python (Join-Path $PSScriptRoot "download_diffusion_left_sota.py")
}

Write-Host ""
Write-Host "Pure live smoke test: no dataset save, no video encoding."
Write-Host "Keep one hand near power/stop. This will command the follower arm."
Write-Host ""
Read-Host "Press Enter to start"

& $Python (Join-Path $PSScriptRoot "live_diffusion_left_sota_smoke.py") `
    --config-path "$ConfigPath" `
    --policy-path "$PolicyPath" `
    --duration-s 10 `
    --fps 10 `
    --num-inference-steps 2 `
    --max-relative-target 5 `
    --torch-threads 8 `
    --log-level ERROR
