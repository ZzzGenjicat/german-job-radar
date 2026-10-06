import tempfile
import json
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import app
from radar.store import Store

class ScheduleTests(unittest.TestCase):
    def test_manual_scan_cannot_suppress_the_18_hour_scheduled_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.sqlite';store=Store(db)
            (Path(tmp)/'schedule.json').write_text(json.dumps({'installed':True}))
            now=datetime.fromisoformat('2026-09-22T18:01:00+02:00')
            run=store.start(now,'manual');store.finish(run,now,'complete',[],[],{})
            with patch.object(app,'DB',db),patch.object(app,'DATA',Path(tmp)):self.assertTrue(app.due(now))
            run=store.start(now,'scheduled');store.finish(run,now,'complete',[],[],{})
            with patch.object(app,'DB',db),patch.object(app,'DATA',Path(tmp)):self.assertFalse(app.due(now))

    def test_without_installed_schedule_there_is_no_automatic_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app,'DATA',Path(tmp)),patch.object(app,'DB',Path(tmp)/'test.sqlite'):
                self.assertFalse(app.due(datetime.fromisoformat('2026-10-06T18:01:00+02:00')))

if __name__=='__main__':unittest.main()
