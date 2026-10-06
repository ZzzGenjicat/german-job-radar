"""Exercise scheduling arguments without touching Windows Task Scheduler."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


WRAPPER = r'''
param([string]$Script, [string]$Data, [string]$Exe, [string]$Capture)
$ErrorActionPreference = 'Stop'
function New-ScheduledTaskAction { param($Execute, $Argument, $WorkingDirectory) @{execute=$Execute;arguments=$Argument;working=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$Once, $At, $RepetitionInterval) @{} }
function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable, [switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries, $ExecutionTimeLimit, $MultipleInstances) @{} }
function New-ScheduledTaskPrincipal { param($UserId, $LogonType, $RunLevel) @{} }
function Register-ScheduledTask {
    param($TaskName, $Action, $Trigger, $Settings, $Principal, $Description, [switch]$Force)
    @{task=$TaskName;action=$Action} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Capture -Encoding UTF8
}
function Get-ScheduledTask { param($TaskName) [pscustomobject]@{TaskName=$TaskName;State='Ready'} }
& $Script -DataDirectory $Data -Executable $Exe | Out-Null
'''


@unittest.skipUnless(os.name == 'nt', 'Windows script')
class ScheduleScriptTests(unittest.TestCase):
    def run_schedule(self, root, data, exe=''):
        wrapper = root / 'mock-scheduler.ps1'
        wrapper.write_text(WRAPPER, encoding='utf-8-sig')
        capture = root / 'capture.json'
        script = Path(__file__).resolve().parents[1] / 'schedule.ps1'
        env = os.environ.copy()
        env['JOB_RADAR_PYTHON'] = sys.executable
        env['JOB_RADAR_DATA_DIR'] = str(root / 'must-not-use-env')
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.run([str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(wrapper),
                        '-Script', str(script), '-Data', str(data), '-Exe', str(exe), '-Capture', str(capture)],
                       env=env, check=True, capture_output=True, timeout=20)
        return json.loads(capture.read_text(encoding='utf-8-sig'))

    def test_desktop_schedule_uses_explicit_data_and_survives_executable_move(self):
        with tempfile.TemporaryDirectory(prefix='Schedule 空格 ') as tmp:
            root = Path(tmp); exe = root / 'first.exe'; exe.touch()
            data = root / '用户数据'
            first = self.run_schedule(root, data, exe)
            self.assertTrue(first['task'].startswith('GermanJobRadar-Desktop-'))
            self.assertIn(str(data), first['action']['arguments'])
            self.assertIn('--data-dir', first['action']['arguments'])
            self.assertIn('--due', first['action']['arguments'])
            self.assertFalse((root / 'must-not-use-env').exists())
            moved = root / 'moved.exe'; moved.touch()
            second = self.run_schedule(root, data, moved)
            self.assertEqual(first['task'], second['task'])
            self.assertEqual(second['action']['execute'], str(moved))
            other = self.run_schedule(root, root / 'other-user-data', moved)
            self.assertNotEqual(first['task'], other['task'])

    def test_source_and_desktop_cannot_reuse_each_others_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / 'data'; exe = root / 'app.exe'; exe.touch()
            source = self.run_schedule(root, data)
            desktop = self.run_schedule(root, data, exe)
            source_again = self.run_schedule(root, data)
            self.assertNotEqual(source['task'], desktop['task'])
            self.assertEqual(source['task'], source_again['task'])
            self.assertIn(str(data), source['action']['arguments'])
            self.assertTrue((data / 'schedule.json').is_file())


if __name__ == '__main__': unittest.main()
