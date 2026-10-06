param([string]$Python)
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $Python) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $Python = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -ne 0) { $Python = $null }
    }
    if (-not $Python) {
        $command = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($command) { $Python = $command.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Install Python 3.11+ from python.org, then run setup.ps1 again. You can also pass -Python "C:\path\to\python.exe".'
}
& $Python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
$venv = Join-Path $radarRoot '.venv'
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install -r (Join-Path $radarRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network connection and rerun setup.ps1.' }
Write-Output 'Ready. Run launch.ps1 or double-click the CMD launcher. No automatic scan or scheduled task has been enabled.'
