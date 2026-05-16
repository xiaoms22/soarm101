param(
    [string]$DatasetName = "so101-left-final-50",
    [int]$ExpectedEpisodes = 50,
    [string]$Python = "",
    [switch]$NoReviewFrames
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$DatasetRoot = Join-Path $RepoRoot "data\$DatasetName"

if (-not (Test-Path $DatasetRoot)) {
    throw "Dataset not found: $DatasetRoot"
}

$argsList = @(
    (Join-Path $PSScriptRoot "validate_final_pilot.py"),
    "--root", $DatasetRoot,
    "--expected-episodes", "$ExpectedEpisodes",
    "--expected-fps", "10"
)

if (-not $NoReviewFrames) {
    $argsList += "--extract-review-frames"
}

& $Python @argsList
