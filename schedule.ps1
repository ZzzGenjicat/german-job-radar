param([switch]$Remove, [string]$Executable = '', [string]$DataDirectory = '', [string]$Time = '')
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
    try { $saved = Get-Content -LiteralPath $radarConfig -Raw | ConvertFrom-Json }
    catch { $saved = $null }
    if ($saved.taskName -match ('^' + $radarTaskPrefix + '[A-Fa-f0-9]{10}$')) { $radarTaskName = $saved.taskName }
}
$radarTime = if ($Time) { $Time } elseif ($saved.time) { $saved.time } else { '18:00' }
if ($radarTime -notmatch '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$') { throw 'Schedule time must be HH:MM between 00:00 and 23:59.' }
function Write-RadarSchedule {
    param($Values)
    $radarTemporary = Join-Path $radarData ('schedule-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [System.IO.File]::WriteAllText($radarTemporary, ($Values | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
        if (Test-Path -LiteralPath $radarConfig) { [System.IO.File]::Replace($radarTemporary, $radarConfig, [NullString]::Value) }
        else { [System.IO.File]::Move($radarTemporary, $radarConfig) }
    } finally {
        if (Test-Path -LiteralPath $radarTemporary) { Remove-Item -LiteralPath $radarTemporary }
    }
}
New-Item -ItemType Directory -Path $radarData -Force | Out-Null
if ($Remove) {
    Unregister-ScheduledTask -TaskName $radarTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-RadarSchedule @{installed=$false;taskName=$radarTaskName;time=$radarTime;timezone='Europe/Berlin';days='Monday-Friday'}
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
# Berlin's UTC offset is a whole number of hours in both summer and winter.
# Wake at the selected minute of each UTC hour; app.py applies the configured
# Berlin hour/weekdays and once-per-day gate. An explicit UTC boundary also
# avoids relying on the host computer's timezone or local DST rules.
$radarNowUtc = [DateTimeOffset]::UtcNow
$radarNextWake = [DateTimeOffset]::new($radarNowUtc.Year, $radarNowUtc.Month, $radarNowUtc.Day, $radarNowUtc.Hour, [int]$radarTime.Substring(3, 2), 0, [TimeSpan]::Zero)
if ($radarNextWake -le $radarNowUtc) { $radarNextWake = $radarNextWake.AddHours(1) }
$radarTrigger = New-ScheduledTaskTrigger -Once -At $radarNextWake.LocalDateTime -RepetitionInterval (New-TimeSpan -Hours 1)
$radarTrigger.StartBoundary = $radarNextWake.ToString('yyyy-MM-ddTHH:mm:sszzz')
$radarSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew
$radarUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$radarPrincipal = New-ScheduledTaskPrincipal -UserId $radarUser -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $radarTaskName -Action $radarAction -Trigger $radarTrigger -Settings $radarSettings -Principal $radarPrincipal -Description ('Local German job reader. Crawls once after ' + $radarTime + ' Europe/Berlin on weekdays; saves accurate snapshots and query evidence.') -Force | Out-Null
New-Item -ItemType Directory -Path $radarData -Force | Out-Null
Write-RadarSchedule @{installed=$true;taskName=$radarTaskName;timezone='Europe/Berlin';time=$radarTime;days='Monday-Friday';installedAt=(Get-Date).ToString('o')}
Get-ScheduledTask -TaskName $radarTaskName | Select-Object TaskName,State
