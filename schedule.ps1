param([switch]$Remove, [string]$Executable = '', [string]$DataDirectory = '')
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$radarData = Join-Path $radarRoot 'data'
if ($Executable) {
    $Executable = (Resolve-Path -LiteralPath $Executable).Path
    $radarRoot = Split-Path -Parent $Executable
    $radarData = Join-Path $env:LOCALAPPDATA 'GermanJobRadar'
}
if ($DataDirectory) { $radarData = $DataDirectory }
elseif ($env:JOB_RADAR_DATA_DIR) { $radarData = $env:JOB_RADAR_DATA_DIR }
if (-not [System.IO.Path]::IsPathRooted($radarData)) { throw 'Data directory must be absolute.' }
$radarData = [System.IO.Path]::GetFullPath($radarData)
$radarConfig = Join-Path $radarData 'schedule.json'
$rootHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($radarData.ToLowerInvariant()))).Replace('-', '').Substring(0, 10)
$radarTaskPrefix = $(if ($Executable) { 'GermanJobRadar-Desktop-' } else { 'GermanJobRadar-' })
$radarTaskName = $radarTaskPrefix + $rootHash
if (Test-Path -LiteralPath $radarConfig) {
    $saved = Get-Content -LiteralPath $radarConfig -Raw | ConvertFrom-Json
    if ($saved.taskName -match ('^' + $radarTaskPrefix + '[A-Fa-f0-9]{10}$')) { $radarTaskName = $saved.taskName }
}
New-Item -ItemType Directory -Path $radarData -Force | Out-Null
if ($Remove) {
    Unregister-ScheduledTask -TaskName $radarTaskName -Confirm:$false -ErrorAction SilentlyContinue
    @{installed=$false; taskName=$radarTaskName} | ConvertTo-Json | Set-Content -LiteralPath $radarConfig -Encoding UTF8
    Write-Output 'Schedule removed; job history preserved.'
    exit
}
if ($Executable) {
    $radarDataArgument = Join-Path $radarData '.'
    $radarAction = New-ScheduledTaskAction -Execute $Executable -Argument ('--data-dir "' + $radarDataArgument + '" --due') -WorkingDirectory $radarRoot
} else {
    . (Join-Path $radarRoot 'runtime.ps1')
    $radarPython = Get-RadarPython -Root $radarRoot
    $radarDataArgument = Join-Path $radarData '.'
    $radarAction = New-ScheduledTaskAction -Execute $radarPython -Argument ('"' + (Join-Path $radarRoot 'app.py') + '" --data-dir "' + $radarDataArgument + '" --due') -WorkingDirectory $radarRoot
}
# Hourly wake-up is timezone independent; app.py gates actual crawling to
# the first successful run after 18:00 Europe/Berlin on Monday-Friday.
$radarNextHour = (Get-Date).Date.AddHours((Get-Date).Hour + 1)
$radarTrigger = New-ScheduledTaskTrigger -Once -At $radarNextHour -RepetitionInterval (New-TimeSpan -Hours 1)
$radarSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew
$radarUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$radarPrincipal = New-ScheduledTaskPrincipal -UserId $radarUser -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $radarTaskName -Action $radarAction -Trigger $radarTrigger -Settings $radarSettings -Principal $radarPrincipal -Description 'Local German job reader. Crawls once after 18:00 Europe/Berlin on weekdays; saves accurate snapshots and query evidence.' -Force | Out-Null
New-Item -ItemType Directory -Path $radarData -Force | Out-Null
@{installed=$true;taskName=$radarTaskName;timezone='Europe/Berlin';time='18:00';days='Monday-Friday';installedAt=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $radarConfig -Encoding UTF8
Get-ScheduledTask -TaskName $radarTaskName | Select-Object TaskName,State
