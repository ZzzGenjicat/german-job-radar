import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from radar.store import Store

def job(key):
    return dict(key=key,classification='review',title='Praktikum '+key,company='Example',location='Berlin',url='https://example.com/jobs/'+key)

class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite')
    def tearDown(self):self.tmp.cleanup()
    def save(self,stamp,kind='scheduled',status='complete',jobs=None):
        at=datetime.fromisoformat(stamp);run=self.store.start(at,kind)
        self.store.finish(run,at,status,jobs or [],[],{})
        return run
    def view(self,stamp):return self.store.view(datetime.fromisoformat(stamp))
    def test_manual_16_replaces_yesterday_and_18_only_adds_c(self):
        self.save('2026-09-21T18:10:00+02:00')
        manual=self.save('2026-09-22T16:00:00+02:00','manual',jobs=[job('A'),job('B')])
        self.assertEqual(self.view('2026-09-22T16:10:00+02:00')['snapshot']['id'],manual)
        self.assertEqual(self.view('2026-09-22T16:10:00+02:00')['mode'],'manual')
        self.save('2026-09-22T18:00:00+02:00',jobs=[job('A'),job('B'),job('C')])
        rows=self.view('2026-09-22T18:10:00+02:00')['snapshot']['jobs']
        self.assertEqual([j['key'] for j in rows if j['is_new']],['C'])
        self.assertEqual(len(rows),3)
    def test_failed_scan_does_not_consume_newness(self):
        self.save('2026-09-22T13:00:00+02:00','manual','failed',[job('A')])
        self.save('2026-09-22T16:00:00+02:00','manual',jobs=[job('A')])
        self.assertTrue(self.view('2026-09-22T16:10:00+02:00')['snapshot']['jobs'][0]['is_new'])
    def test_official_link_dedups_city_spelling_variants(self):
        a=job('A');a['apply_url']='https://employer.example/careers/123?utm_source=a';a['apply_status']='verified'
        b=job('B');b['apply_url']='https://employer.example/careers/123?utm_source=b';b['apply_status']='verified'
        self.save('2026-09-22T13:00:00+02:00','manual',jobs=[a])
        self.save('2026-09-22T16:00:00+02:00','manual',jobs=[b])
        self.assertFalse(self.view('2026-09-22T16:10:00+02:00')['snapshot']['jobs'][0]['is_new'])
if __name__=='__main__':unittest.main()
