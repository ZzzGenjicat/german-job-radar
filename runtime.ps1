$ErrorActionPreference = 'Stop'

function Get-RadarPython {
    param([string]$Root, [switch]$Console)
    $candidate = Join-Path $Root '.venv\Scripts\python.exe'
    if ($env:JOB_RADAR_PYTHON) { $candidate = $env:JOB_RADAR_PYTHON }
    elseif (-not (Test-Path -LiteralPath $candidate)) {
        # Optional local override, never part of a release.
        $runtimeConfig = Join-Path $Root 'data\runtime.json'
        if (Test-Path -LiteralPath $runtimeConfig) {
            $candidate = (Get-Content -LiteralPath $runtimeConfig -Raw | ConvertFrom-Json).python
        }
    }
    if (-not $candidate -or -not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw 'Python environment missing. Run setup.ps1 first, or set JOB_RADAR_PYTHON.'
    }
    $candidate = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $Console) {
        $windowless = Join-Path (Split-Path -Parent $candidate) 'pythonw.exe'
        if (Test-Path -LiteralPath $windowless) { return $windowless }
    }
    return $candidate
}
