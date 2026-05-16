param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"
$DatasetName = "so101-left-final-pilot"
$RepoId = "xiaoms22/$DatasetName"
$DatasetRoot = Join-Path $RepoRoot "data\$DatasetName"

if (Test-Path $DatasetRoot) {
    throw "Dataset already exists: $DatasetRoot. Use a new suffix such as so101-left-final-pilot-v2, or archive the old directory first."
}

Write-Host ""
Write-Host "SO-ARM101 final pilot collection"
Write-Host "Dataset: $RepoId"
Write-Host "Root:    $DatasetRoot"
Write-Host ""
Write-Host "Checklist before continuing:"
Write-Host "  1. Final tray is fixed."
Write-Host "  2. Final object starts in the LEFT zone."
Write-Host "  3. Fixed and handeye cameras are fixed and unobstructed."
Write-Host "  4. Follower is at the shared home pose."
Write-Host "  5. COM3 follower and COM4 leader are powered."
Write-Host "  6. If calibration prompt appears, press Enter to use existing calibration."
Write-Host ""
Write-Host "Episode controls:"
Write-Host "  Right Arrow: finish and save current episode."
Write-Host "  Left Arrow: discard and rerecord current episode."
Write-Host "  Esc: stop collection."
Write-Host ""
Write-Host "Note: display_data is disabled because this environment does not have the Rerun Viewer executable."
Write-Host ""
Read-Host "Press Enter to start 10-episode collection"

& $Python -m lerobot.scripts.lerobot_record `
    --config_path="$ConfigPath" `
    --dataset.repo_id="$RepoId" `
    --dataset.root="$DatasetRoot" `
    --dataset.num_episodes=10 `
    --dataset.episode_time_s=30 `
    --dataset.reset_time_s=10 `
    --dataset.push_to_hub=false `
    --display_data=false `
    --play_sounds=true
