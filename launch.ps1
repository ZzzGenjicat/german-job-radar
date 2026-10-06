$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $radarRoot 'runtime.ps1')
$radarPython = Get-RadarPython -Root $radarRoot
Start-Process -FilePath $radarPython -ArgumentList @(('"' + (Join-Path $radarRoot 'app.py') + '"'), '--open') -WorkingDirectory $radarRoot -WindowStyle Hidden
