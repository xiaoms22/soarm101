param(
    [ValidateSet("scratch", "finetune", "diffusion-scratch", "diffusion-finetune", "act", "smolvla")]
    [string]$Variant = "diffusion-scratch",
    [double]$DurationS = 10,
    [int]$NumInferenceSteps = 2,
    [double]$MaxRelativeTarget = 10,
    [double]$ActionEmaAlpha = 0.35,
    [string]$Python = "",
    [switch]$NoActionLog
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$ConfigPath = Join-Path $RepoRoot "record_config.yaml"
$LiveScript = Join-Path $PSScriptRoot "live_diffusion_left_sota_smoke.py"

if ($Variant -eq "scratch") {
    $Variant = "diffusion-scratch"
}

if ($Variant -eq "finetune") {
    $Variant = "diffusion-finetune"
}

if ($Variant -eq "diffusion-scratch") {
    $PolicyPath = Join-Path $RepoRoot "models\diffusion-left-final-50-scratch-10k"
} elseif ($Variant -eq "diffusion-finetune") {
    $PolicyPath = Join-Path $RepoRoot "models\diffusion-left-final-50-from-006000-4k"
} elseif ($Variant -eq "act") {
    $PolicyPath = Join-Path $RepoRoot "models\act-left-final-50-10k"
} elseif ($Variant -eq "smolvla") {
    $PolicyPath = Join-Path $RepoRoot "models\smolvla-left-final-50-20k"
} else {
    throw "Unsupported variant: $Variant"
}

if (-not (Test-Path $PolicyPath)) {
    throw "Policy path not found: $PolicyPath"
}

$argsList = @(
    $LiveScript,
    "--config-path", $ConfigPath,
    "--policy-path", $PolicyPath,
    "--duration-s", "$DurationS",
    "--fps", "10",
    "--num-inference-steps", "$NumInferenceSteps",
    "--max-relative-target", "$MaxRelativeTarget",
    "--motor-retries", "5",
    "--warmup-reads", "3",
    "--action-ema-alpha", "$ActionEmaAlpha",
    "--torch-threads", "8",
    "--log-level", "ERROR"
)

if (-not $NoActionLog) {
    $LogDir = Join-Path $RepoRoot "outputs\rollout_logs"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $ActionLog = Join-Path $LogDir "left_final_50_${Variant}_smoke_$ts.csv"
    $argsList += @("--action-log", $ActionLog)
}

& $Python @argsList

if (-not $NoActionLog) {
    Write-Host "ACTION_LOG=$ActionLog"
}
