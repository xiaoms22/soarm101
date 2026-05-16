param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $RepoRoot "scripts\resolve_project_python.ps1")
$Python = Resolve-ProjectPython $Python
$DatasetRoot = Join-Path $RepoRoot "data\so101-left-final-pilot"

& $Python (Join-Path $PSScriptRoot "validate_final_pilot.py") `
    --root "$DatasetRoot" `
    --expected-episodes 10 `
    --expected-fps 10 `
    --extract-review-frames
