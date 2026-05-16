param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$PolicyPath = Join-Path $RepoRoot "models\diffusion-left-sota"
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvalRoot = Join-Path $RepoRoot "data\eval_so101_local_smoke_$Stamp"

if (-not (Test-Path (Join-Path $PolicyPath "model.safetensors"))) {
    Write-Host "Policy is missing. Downloading diffusion-left-sota first..."
    & $Python (Join-Path $PSScriptRoot "download_diffusion_left_sota.py")
}

Write-Host ""
Write-Host "Policy path: $PolicyPath"
Write-Host "Eval data:   $EvalRoot"
Write-Host ""
Write-Host "Safety checklist before continuing:"
Write-Host "  1. Put the follower arm in a clear workspace."
Write-Host "  2. Keep one hand near power/stop."
Write-Host "  3. Expect poor task performance; this is only a pipeline smoke test."
Write-Host "  4. Press Right Arrow to end the episode early, or Esc to stop recording."
Write-Host ""
Read-Host "Press Enter to start the local policy smoke test"

& $Python -m lerobot.scripts.lerobot_record `
    --config_path="$ConfigPath" `
    --policy.path="$PolicyPath" `
    --policy.device=cpu `
    --policy.use_amp=false `
    --policy.num_inference_steps=4 `
    --robot.max_relative_target=10.0 `
    --dataset.repo_id=xiaoms22/eval_so101_local_smoke `
    --dataset.root="$EvalRoot" `
    --dataset.num_episodes=1 `
    --dataset.episode_time_s=10 `
    --dataset.reset_time_s=0 `
    --dataset.push_to_hub=false `
    --display_data=false `
    --play_sounds=false
