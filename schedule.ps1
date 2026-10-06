param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$radarConfig = Join-Path $radarRoot 'data\schedule.json'
$rootHash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($radarRoot))).Replace('-', '').Substring(0, 10)
$radarTaskName = 'GermanJobRadar-' + $rootHash
if (Test-Path -LiteralPath $radarConfig) {
    $saved = Get-Content -LiteralPath $radarConfig -Raw | ConvertFrom-Json
    if ($saved.taskName -match '^GermanJobRadar-[A-Za-z0-9-]+$') { $radarTaskName = $saved.taskName }
}
New-Item -ItemType Directory -Path (Join-Path $radarRoot 'data') -Force | Out-Null
if ($Remove) {
    Unregister-ScheduledTask -TaskName $radarTaskName -Confirm:$false -ErrorAction SilentlyContinue
    @{installed=$false; taskName=$radarTaskName} | ConvertTo-Json | Set-Content -LiteralPath $radarConfig -Encoding UTF8
    Write-Output 'Schedule removed; job history preserved.'
    exit
}
. (Join-Path $radarRoot 'runtime.ps1')
$radarPython = Get-RadarPython -Root $radarRoot
$radarAction = New-ScheduledTaskAction -Execute $radarPython -Argument ('"' + (Join-Path $radarRoot 'app.py') + '" --due') -WorkingDirectory $radarRoot
# Hourly wake-up is timezone independent; app.py gates actual crawling to
# the first successful run after 18:00 Europe/Berlin on Monday-Friday.
$radarNextHour = (Get-Date).Date.AddHours((Get-Date).Hour + 1)
$radarTrigger = New-ScheduledTaskTrigger -Once -At $radarNextHour -RepetitionInterval (New-TimeSpan -Hours 1)
$radarSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew
$radarUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$radarPrincipal = New-ScheduledTaskPrincipal -UserId $radarUser -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $radarTaskName -Action $radarAction -Trigger $radarTrigger -Settings $radarSettings -Principal $radarPrincipal -Description 'Local German job reader. Crawls once after 18:00 Europe/Berlin on weekdays; saves accurate snapshots and query evidence.' -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $radarRoot 'data') -Force | Out-Null
@{installed=$true;taskName=$radarTaskName;timezone='Europe/Berlin';time='18:00';days='Monday-Friday';installedAt=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $radarConfig -Encoding UTF8
Get-ScheduledTask -TaskName $radarTaskName | Select-Object TaskName,State
