param(
    [string]$DatasetName = "so101-left-final-50",
    [int]$TargetEpisodes = 50,
    [int]$EpisodeTimeS = 30,
    [int]$ResetTimeS = 10,
    [string]$Python = "",
    [switch]$Resume
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"
$RepoId = "xiaoms22/$DatasetName"
$DatasetRoot = Join-Path $RepoRoot "data\$DatasetName"

if ($TargetEpisodes -le 0) {
    throw "TargetEpisodes must be positive."
}

$existingEpisodes = 0
if (Test-Path $DatasetRoot) {
    if (-not $Resume) {
        throw "Dataset already exists: $DatasetRoot. Use -Resume to append remaining episodes, or choose a new -DatasetName."
    }

    $InfoPath = Join-Path $DatasetRoot "meta\info.json"
    if (-not (Test-Path $InfoPath)) {
        throw "Cannot resume because metadata is missing: $InfoPath"
    }

    $info = Get-Content $InfoPath -Raw | ConvertFrom-Json
    $existingEpisodes = [int]$info.total_episodes
    if ($existingEpisodes -ge $TargetEpisodes) {
        throw "Dataset already has $existingEpisodes episodes, target is $TargetEpisodes. Nothing to record."
    }
} elseif ($Resume) {
    throw "Cannot resume because dataset does not exist: $DatasetRoot"
}

$EpisodesToRecord = $TargetEpisodes - $existingEpisodes

Write-Host ""
Write-Host "SO-ARM101 left-final 50-episode collection"
Write-Host "Dataset:        $RepoId"
Write-Host "Root:           $DatasetRoot"
Write-Host "Target total:   $TargetEpisodes episodes"
Write-Host "Existing:       $existingEpisodes episodes"
Write-Host "This session:   $EpisodesToRecord episodes"
Write-Host ""
Write-Host "Checklist before continuing:"
Write-Host "  1. Use the compact/shared start pose, not a lowered pre-grasp pose."
Write-Host "  2. Final tray, object, fixed/top camera, and handeye/wrist camera are fixed."
Write-Host "  3. Camera mapping remains fixed=Camera 0, handeye=Camera 2."
Write-Host "  4. Object starts in the LEFT zone with small position variations only."
Write-Host "  5. COM3 follower and COM4 leader are powered; teleoperation is normal."
Write-Host "  6. Each episode must show: approach, lower enough, close gripper, lift, place, release."
Write-Host "  7. If a grasp fails, discard and rerecord; do not keep correction/recovery motions."
Write-Host ""
Write-Host "Episode controls:"
Write-Host "  Right Arrow: finish and save current episode."
Write-Host "  Left Arrow: discard and rerecord current episode."
Write-Host "  Esc: stop collection."
Write-Host ""
Write-Host "Note: display_data is disabled because this environment does not have the Rerun Viewer executable."
Write-Host ""
Read-Host "Press Enter to start this collection session"

$argsList = @(
    "-m", "lerobot.scripts.lerobot_record",
    "--config_path=$ConfigPath",
    "--dataset.repo_id=$RepoId",
    "--dataset.root=$DatasetRoot",
    "--dataset.num_episodes=$EpisodesToRecord",
    "--dataset.episode_time_s=$EpisodeTimeS",
    "--dataset.reset_time_s=$ResetTimeS",
    "--dataset.push_to_hub=false",
    "--display_data=false",
    "--play_sounds=true"
)

if ($Resume) {
    $argsList += "--resume=true"
}

& $Python @argsList
