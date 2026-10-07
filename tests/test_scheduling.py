import json
import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import app
from radar.core import edition_for
from radar.store import Store


class ConfigurableScheduleTests(unittest.TestCase):
    def test_legacy_and_new_settings_default_to_1800(self):
        from radar.scheduling import read_schedule
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(read_schedule(folder)['time'], '18:00')
            self.assertFalse(read_schedule(folder)['installed'])
            (folder / 'schedule.json').write_text(json.dumps({'installed': True}))
            self.assertEqual(read_schedule(folder)['time'], '18:00')
            self.assertTrue(read_schedule(folder)['installed'])

    def test_time_validation_is_strict_and_corrupt_configuration_fails_closed(self):
        from radar.scheduling import read_schedule, validate_time
        for value in ('00:00', '17:35', '23:59'):
            self.assertEqual(validate_time(value), value)
        for value in ('24:00', '18:60', '6:00', '18:00;echo', None, 1800):
            with self.assertRaises(ValueError): validate_time(value)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'schedule.json').write_text(json.dumps({'installed': True, 'time': 'invalid'}))
            self.assertFalse(read_schedule(Path(tmp))['installed'])

    def test_changed_minute_triggers_once_and_manual_scan_does_not_suppress_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); db = folder / 'jobs.sqlite'; store = Store(db)
            config = folder / 'schedule.json'
            config.write_text(json.dumps({'installed': True, 'time': '17:35'}))
            before = datetime.fromisoformat('2026-09-22T17:34:59+02:00')
            at = datetime.fromisoformat('2026-09-22T17:35:00+02:00')
            manual = store.start(before, 'manual'); store.finish(manual, before, 'complete', [], [], {})
            with patch.object(app, 'DATA', folder), patch.object(app, 'DB', db):
                self.assertFalse(app.due(before))
                self.assertTrue(app.due(at))
                run = store.start(at, 'scheduled'); store.finish(run, at, 'complete', [], [], {})
                self.assertTrue(store.scheduled_today('2026-09-22'))
                self.assertFalse(app.due(at))
                config.write_text(json.dumps({'installed': True, 'time': '19:10'}))
                self.assertFalse(app.due(datetime.fromisoformat('2026-09-22T19:10:00+02:00')))

    def test_custom_time_respects_berlin_dst_and_weekends(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'schedule.json').write_text(json.dumps({'installed': True, 'time': '08:15'}))
            with patch.object(app, 'DATA', folder), patch.object(app, 'DB', folder / 'jobs.sqlite'):
                self.assertFalse(app.due(datetime.fromisoformat('2026-10-06T06:14:59+00:00')))
                self.assertTrue(app.due(datetime.fromisoformat('2026-10-06T06:15:00+00:00')))
                self.assertFalse(app.due(datetime.fromisoformat('2026-10-27T07:14:59+00:00')))
                self.assertTrue(app.due(datetime.fromisoformat('2026-10-27T07:15:00+00:00')))
                self.assertFalse(app.due(datetime.fromisoformat('2026-10-10T10:00:00+00:00')))

    def test_custom_time_controls_edition_boundary_and_midnight_catchup(self):
        self.assertEqual(edition_for(datetime.fromisoformat('2026-10-06T17:34:59+02:00'), '17:35'), '2026-10-05')
        self.assertEqual(edition_for(datetime.fromisoformat('2026-10-06T17:35:00+02:00'), '17:35'), '2026-10-06')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); store = Store(folder / 'jobs.sqlite')
            (folder / 'schedule.json').write_text(json.dumps({'installed': True, 'time': '00:00'}))
            now = datetime.fromisoformat('2026-10-06T00:00:00+02:00')
            run = store.start(now, 'catchup'); store.finish(run, now, 'complete', [], [], {})
            self.assertTrue(store.scheduled_today('2026-10-06'))
            self.assertEqual(store.view(now)['target_date'], '2026-10-06')

    def test_application_passes_selected_time_to_windows_scheduler(self):
        with patch.object(app, 'FROZEN', True), patch('app.subprocess.run') as command:
            command.return_value.returncode = 0
            app.configure_schedule(True, '17:35')
            args = command.call_args.args[0]
            self.assertEqual(args[args.index('-Time') + 1], '17:35')
            self.assertEqual(command.call_args.kwargs['cwd'], app.ROOT)
        with patch('app.subprocess.run') as command:
            with self.assertRaises(ValueError): app.configure_schedule(True, '25:00')
            command.assert_not_called()

    def test_settings_api_requires_origin_token_and_valid_time(self):
        def handler(payload, origin=app.ORIGIN, token=app.TOKEN):
            request = app.Handler.__new__(app.Handler)
            request.path = '/api/schedule'
            body = json.dumps(payload).encode()
            request.headers = {'Host': f'127.0.0.1:{app.PORT}', 'Origin': origin,
                               'X-Radar-Token': token, 'Content-Length': str(len(body))}
            request.rfile = io.BytesIO(body)
            request.respond = Mock()
            request.do_POST()
            return request.respond.call_args.args[0]

        with patch('app.subprocess.run') as command:
            command.return_value.returncode = 0
            self.assertEqual(handler({'enabled': False, 'time': '17:35'}, token=''), 403)
            self.assertEqual(handler({'enabled': False, 'time': '17:35'}, origin='https://example.test'), 403)
            for payload in ({'enabled': False, 'time': '24:00'}, {'enabled': 1, 'time': '17:35'},
                            {'enabled': False}, {'enabled': False, 'time': '17:35', 'extra': True}):
                self.assertEqual(handler(payload), 400)
            command.assert_not_called()
            with tempfile.TemporaryDirectory() as tmp, patch.object(app, 'DATA', Path(tmp)):
                self.assertEqual(handler({'enabled': False, 'time': '17:35'}), 200)
                self.assertIn('-Remove', command.call_args.args[0])

    def test_delayed_scheduled_worker_rechecks_completion_after_lock(self):
        import radar.scan as scan
        now = datetime.fromisoformat('2026-10-06T18:10:00+02:00')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); db = folder / 'jobs.sqlite'; store = Store(db)
            run = store.start(now, 'scheduled')
            store.finish(run, now, 'complete', [], [], {})
            source = {'id': 'synthetic', 'name': 'Synthetic', 'kind': 'regional', 'base': 'https://example.test', 'enabled': True}
            with patch.object(scan, 'DATA', folder), patch.object(scan, 'DB', db), patch.object(scan, 'now_utc', return_value=now), \
                    patch.object(Store, 'source_settings', return_value=[source]), \
                    patch.object(Store, 'keywords', return_value=[{'term': 'Synthetic', 'enabled': True}]), \
                    patch.object(scan, 'parse_search', return_value={'parsed': True, 'items': [], 'has_more': False}), \
                    patch.object(scan, 'Fetcher') as fetcher:
                fetcher.return_value.get.return_value = {'body': '', 'status': 200}
                for kind in ('scheduled', 'catchup'):
                    result = scan.run_scan(kind)
                    self.assertEqual(result['status'], 'skipped')
                fetcher.assert_not_called()
            with store.connect() as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM scans').fetchone()[0], 1)


if __name__ == '__main__': unittest.main()
