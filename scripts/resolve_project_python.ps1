function Resolve-ProjectPython {
    param(
        [string]$Python = ""
    )

    if ([string]::IsNullOrWhiteSpace($Python)) {
        if (-not [string]::IsNullOrWhiteSpace($env:SOARM101_PYTHON)) {
            $Python = $env:SOARM101_PYTHON
        } elseif (-not [string]::IsNullOrWhiteSpace($env:CONDA_PREFIX)) {
            $Candidate = Join-Path $env:CONDA_PREFIX "python.exe"
            if (Test-Path $Candidate) {
                $Python = $Candidate
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($Python)) {
        $Python = "python"
    }

    if (Test-Path $Python) {
        return (Resolve-Path $Python).Path
    }

    $Command = Get-Command $Python -ErrorAction SilentlyContinue
    if ($null -eq $Command) {
        throw "Python executable not found. Activate the LeRobot environment, pass -Python, or set SOARM101_PYTHON."
    }

    return $Command.Source
}
