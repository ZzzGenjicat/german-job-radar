import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class DesktopTests(unittest.TestCase):
    def test_source_keeps_existing_data_location(self):
        from radar.runtime import resolve_paths
        root = Path('C:/source/radar')
        self.assertEqual(resolve_paths(root, False, {}), (root, root / 'data'))

    def test_frozen_data_survives_temporary_bundle_and_executable_moves(self):
        from radar.runtime import resolve_paths
        env = {'LOCALAPPDATA': 'C:/user/local'}
        first = resolve_paths(Path('C:/temp/_MEI123'), True, env)
        second = resolve_paths(Path('C:/temp/_MEI456'), True, env)
        self.assertEqual(first[1], Path('C:/user/local/GermanJobRadar'))
        self.assertEqual(first[1], second[1])
        self.assertNotEqual(first[0], second[0])

    def test_test_data_override_must_be_absolute(self):
        from radar.runtime import resolve_paths
        with self.assertRaises(ValueError):
            resolve_paths(Path('C:/root'), True, {'JOB_RADAR_DATA_DIR': 'relative'})
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(resolve_paths(Path(tmp), True, {'JOB_RADAR_DATA_DIR': tmp})[1], Path(tmp))

    def test_port_validation(self):
        from radar.runtime import app_port
        self.assertEqual(app_port({}), 48218)
        self.assertEqual(app_port({'JOB_RADAR_PORT': '48219'}), 48219)
        for value in ('0', '-1', '999999', 'invalid'):
            with self.assertRaises(ValueError): app_port({'JOB_RADAR_PORT': value})

    def test_desktop_credentials_are_separate_from_source_and_other_data_directories(self):
        from radar.runtime import credential_target
        self.assertEqual(credential_target('source', False), 'GermanJobRadar/OpenAI')
        self.assertNotEqual(credential_target('one', True), credential_target('source', False))
        self.assertNotEqual(credential_target('one', True), credential_target('two', True))

    def test_health_rejects_another_installations_database(self):
        response = io.StringIO(json.dumps({'app': app.APP_ID, 'instance': 'another-installation'}))
        with patch('app.urllib.request.urlopen', return_value=response):
            self.assertFalse(app.healthy())

    def test_frozen_launcher_restarts_its_executable_without_a_python_script(self):
        with patch.object(app.sys, 'frozen', True, create=True), patch.object(app.sys, 'executable', 'C:/apps/GermanJobRadar.exe'), patch.object(app, 'healthy', side_effect=[False, True]), patch('app.subprocess.Popen') as spawn, patch('app.webbrowser.open') as browser:
            app.open_app(open_browser=False)
        self.assertEqual(spawn.call_args.args[0], ['C:/apps/GermanJobRadar.exe', '--serve'])
        self.assertEqual(spawn.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
        self.assertEqual(spawn.call_args.kwargs['env']['JOB_RADAR_DATA_DIR'], str(app.DATA))
        browser.assert_not_called()

    def test_shutdown_rejects_scan_lock_even_after_database_batch_finished(self):
        import radar.scan as scan
        with tempfile.TemporaryDirectory() as tmp, patch.object(scan, 'DATA', Path(tmp)), patch.object(app, 'ACTIVE_WORKERS', set(), create=True), patch.object(app, 'STOP', threading.Event()):
            with scan.ScanLock():
                with self.assertRaises(ValueError): app.begin_shutdown()
            self.assertFalse(app.STOP.is_set())

    def test_shutdown_rejects_queued_work_before_database_start(self):
        with patch.object(app, 'ACTIVE_WORKERS', {object()}, create=True), patch.object(app, 'STOP', threading.Event()):
            with self.assertRaises(ValueError): app.begin_shutdown()
            self.assertFalse(app.STOP.is_set())

    def test_shutdown_prevents_new_scan_admission(self):
        import radar.scan as scan
        with tempfile.TemporaryDirectory() as tmp, patch.object(scan, 'DATA', Path(tmp)), patch.object(app, 'ACTIVE_WORKERS', set(), create=True), patch.object(app, 'STOP', threading.Event()):
            app.begin_shutdown()
            self.assertFalse(app.scan_background('manual'))


if __name__ == '__main__': unittest.main()
