"""Exercise scheduling arguments without touching Windows Task Scheduler."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime


WRAPPER = r'''
param([string]$Script, [string]$Data, [string]$Exe, [string]$Capture, [string]$Time = '', [switch]$Remove)
$ErrorActionPreference = 'Stop'
function New-ScheduledTaskAction { param($Execute, $Argument, $WorkingDirectory) @{execute=$Execute;arguments=$Argument;working=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$Once, $At, $RepetitionInterval) @{at=$At.ToString('o');interval=$RepetitionInterval.TotalSeconds} }
function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable, [switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries, $ExecutionTimeLimit, $MultipleInstances) @{} }
function New-ScheduledTaskPrincipal { param($UserId, $LogonType, $RunLevel) @{} }
function Register-ScheduledTask {
    param($TaskName, $Action, $Trigger, $Settings, $Principal, $Description, [switch]$Force)
    @{task=$TaskName;action=$Action;trigger=$Trigger} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Capture -Encoding UTF8
}
function Unregister-ScheduledTask { param($TaskName, [switch]$Confirm, $ErrorAction) @{removed=$TaskName} | ConvertTo-Json | Set-Content -LiteralPath $Capture -Encoding UTF8 }
function Get-ScheduledTask { param($TaskName) [pscustomobject]@{TaskName=$TaskName;State='Ready'} }
& $Script -DataDirectory $Data -Executable $Exe -Time $Time -Remove:$Remove | Out-Null
'''


@unittest.skipUnless(os.name == 'nt', 'Windows script')
class ScheduleScriptTests(unittest.TestCase):
    def assert_data_argument(self, arguments, expected):
        match = re.search(r'--data-dir "([^"]+)"', arguments)
        self.assertIsNotNone(match)
        # Windows runners can expose a short TEMP alias (RUNNER~1) while
        # PowerShell resolves the same directory to its long name.
        self.assertEqual(Path(match.group(1)).resolve(), expected.resolve())

    def run_schedule(self, root, data, exe='', time='', remove=False):
        wrapper = root / 'mock-scheduler.ps1'
        wrapper.write_text(WRAPPER, encoding='utf-8-sig')
        capture = root / 'capture.json'
        script = Path(__file__).resolve().parents[1] / 'schedule.ps1'
        env = os.environ.copy()
        env['JOB_RADAR_PYTHON'] = sys.executable
        env['JOB_RADAR_DATA_DIR'] = str(root / 'must-not-use-env')
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        command = [str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(wrapper),
                   '-Script', str(script), '-Data', str(data), '-Exe', str(exe), '-Capture', str(capture), '-Time', time]
        if remove: command.append('-Remove')
        subprocess.run(command,
                       env=env, check=True, capture_output=True, timeout=20)
        return json.loads(capture.read_text(encoding='utf-8-sig'))

    def test_desktop_schedule_uses_explicit_data_and_survives_executable_move(self):
        with tempfile.TemporaryDirectory(prefix='Schedule 空格 ') as tmp:
            root = Path(tmp); exe = root / 'first.exe'; exe.touch()
            data = root / '用户数据'
            first = self.run_schedule(root, data, exe)
            self.assertTrue(first['task'].startswith('GermanJobRadar-Desktop-'))
            self.assert_data_argument(first['action']['arguments'], data)
            self.assertIn('--data-dir', first['action']['arguments'])
            self.assertIn('--due', first['action']['arguments'])
            self.assertFalse((root / 'must-not-use-env').exists())
            moved = root / 'moved.exe'; moved.touch()
            second = self.run_schedule(root, data, moved)
            self.assertEqual(first['task'], second['task'])
            self.assertEqual(Path(second['action']['execute']).resolve(), moved.resolve())
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
            self.assert_data_argument(source['action']['arguments'], data)
            self.assertTrue((data / 'schedule.json').is_file())

    def test_selected_minutes_are_preserved_by_trigger_and_disable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / 'data'; exe = root / 'app.exe'; exe.touch()
            result = self.run_schedule(root, data, exe, '17:35')
            config = json.loads((data / 'schedule.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(config['time'], '17:35')
            wake = datetime.fromisoformat(result['trigger']['StartBoundary'])
            self.assertEqual(wake.minute, 35)
            self.assertEqual(wake.utcoffset().total_seconds(), 0)
            self.assertEqual(result['trigger']['interval'], 3600)
            removed = self.run_schedule(root, data, exe, remove=True)
            self.assertEqual(removed['removed'], result['task'])
            config = json.loads((data / 'schedule.json').read_text(encoding='utf-8-sig'))
            self.assertFalse(config['installed'])
            self.assertEqual(config['time'], '17:35')

    def test_invalid_time_does_not_change_prior_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); data = root / 'data'; exe = root / 'app.exe'; exe.touch()
            self.run_schedule(root, data, exe, '18:00')
            before = (data / 'schedule.json').read_bytes()
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_schedule(root, data, exe, '24:00')
            self.assertEqual((data / 'schedule.json').read_bytes(), before)


if __name__ == '__main__': unittest.main()
