param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$PolicyPath = Join-Path $RepoRoot "models\diffusion-left-final-pilot-2k"
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"

if (-not (Test-Path (Join-Path $PolicyPath "model.safetensors"))) {
    throw "Fine-tuned policy is missing: $PolicyPath"
}

Write-Host ""
Write-Host "SO-ARM101 final-pilot fine-tuned policy smoke test."
Write-Host "No dataset save, no video encoding. Keep one hand near power/stop."
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
