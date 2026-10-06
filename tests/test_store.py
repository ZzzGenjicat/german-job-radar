import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from radar.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'test.sqlite')
    def tearDown(self):
        self.tmp.cleanup()
    def save(self, stamp, status='complete', jobs=None):
        at=datetime.fromisoformat(stamp)
        run=self.store.start(at,'manual')
        self.store.finish(run,at,status,jobs or [],[],{'detail_count':1})
        return run
    def test_failed_today_keeps_yesterdays_report(self):
        older=self.save('2026-09-21T18:10:00+02:00')
        self.save('2026-09-22T18:10:00+02:00','failed')
        view=self.store.view(datetime.fromisoformat('2026-09-22T19:00:00+02:00'))
        self.assertEqual(view['snapshot']['id'],older)
        self.assertTrue(view['stale'])
        self.assertEqual(view['latest_attempt']['status'],'failed')
    def test_morning_scan_does_not_claim_yesterdays_edition(self):
        self.save('2026-09-21T09:00:00+02:00')
        view=self.store.view(datetime.fromisoformat('2026-09-21T10:00:00+02:00'))
        self.assertIsNone(view['snapshot']['edition_date'])
        self.assertEqual(view['mode'],'manual')
    def test_first_failed_scan_preserves_current_query_errors(self):
        at=datetime.fromisoformat('2026-10-06T18:10:00+02:00')
        run=self.store.start(at,'manual')
        queries=[{'source':'Example','keyword':'CRM','status':'error','error':'HTTP 403'}]
        self.store.finish(run,at,'failed',[],queries,{'error':'All sources failed'})
        view=self.store.view(at)
        self.assertIsNone(view['snapshot'])
        self.assertEqual(view['latest_attempt']['queries'],queries)
    def test_repeat_across_days_has_no_new_recommendation(self):
        j=dict(key='one',classification='recommended',title='Praktikum KI',rank=5)
        self.save('2026-09-21T18:10:00+02:00',jobs=[j])
        self.save('2026-09-22T18:10:00+02:00',jobs=[j])
        view=self.store.view(datetime.fromisoformat('2026-09-22T19:00:00+02:00'))
        self.assertEqual(view['snapshot']['jobs'][0]['classification'],'previous')
        self.assertEqual(view['snapshot']['stats']['new_count'],0)

if __name__=='__main__':unittest.main()
