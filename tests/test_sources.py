import unittest
from pathlib import Path
from radar.sources import parse_search, parse_detail, application_evidence, SOURCES, test_source

FIX = Path(__file__).parent / 'fixtures'


class SourceTests(unittest.TestCase):
    def test_default_catalog_replaces_broken_suedwest_source(self):
        ids={source['id'] for source in SOURCES}
        self.assertNotIn('suedwest',ids)
        self.assertIn('suedwest-jobs',ids)

    def test_real_regional_search_keeps_keyword_and_row_date(self):
        result = parse_search((FIX/'synthetic-regional-search.html').read_text(encoding='utf-8'), 'https://www.bayern.jobs/jobs?search=Praktikum+KI', 'Praktikum KI')
        self.assertTrue(result['parsed'])
        self.assertGreater(len(result['items']), 5)
        item = result['items'][0]
        self.assertEqual(item['company'], 'Example Motors GmbH')
        self.assertEqual(item['search_terms'], ['Praktikum KI'])
        self.assertTrue(result['has_more'])

    def test_real_detail_uses_own_posting_not_related_jobs(self):
        j = parse_detail((FIX/'synthetic-regional-repost.html').read_text(encoding='utf-8'), 'https://www.bayern.jobs/job/example-17897707')
        self.assertEqual(j['original_posted'], '2026-08-17')
        self.assertEqual(j['posted'], '2026-09-21')
        self.assertEqual(j['company'], 'Example Motors GmbH')
        self.assertEqual(j['location'], 'München')
        self.assertNotIn('Ähnliche Stellenanzeigen', j['description'])

    def test_ba_uses_first_publication_not_modification(self):
        r = parse_search((FIX/'synthetic-ba-search.html').read_text(encoding='utf-8'), 'https://www.arbeitsagentur.de/jobsuche/suche?was=KI', 'KI')
        self.assertEqual(r['items'][0]['posted'], '2026-09-17')
        self.assertEqual(r['items'][0]['company'], 'Example Staffing GmbH')

    def test_ba_detail_preserves_external_application(self):
        j = parse_detail((FIX/'synthetic-ba-detail.html').read_text(encoding='utf-8'), 'https://www.arbeitsagentur.de/jobsuche/jobdetail/example-123')
        self.assertEqual(j['posted'], '2026-09-20')
        self.assertEqual(j['location'], 'Coburg')
        self.assertTrue(j['apply_url'].startswith('https://careers.example.test/'))

    def test_captcha_is_failure_not_zero_results(self):
        self.assertFalse(parse_search('<html>Verify you are human</html>', 'https://www.bayern.jobs/jobs', 'KI')['parsed'])

    def test_generic_career_landing_is_not_verified(self):
        status, _ = application_evidence('<h1>Welcome to our careers</h1><a>Apply now</a>', 'Praktikum KI Automatisierung')
        self.assertEqual(status, 'unverified')
        status, _ = application_evidence('<h1>Praktikum KI Automatisierung</h1><p>This job is no longer available</p>', 'Praktikum KI Automatisierung')
        self.assertEqual(status, 'closed')

    def test_source_probe_distinguishes_supported_and_unsupported(self):
        search=(FIX/'synthetic-regional-search.html').read_text(encoding='utf-8')
        detail=(FIX/'synthetic-regional-repost.html').read_text(encoding='utf-8')
        class Fetcher:
            def get(self,url):return {'body':search if '/jobs?' in url else detail,'url':url,'status':200}
        source={'id':'probe','name':'Probe','base':'https://www.bayern.jobs','region':'Bayern','kind':'regional'}
        result=test_source(source,'Praktikum KI',Fetcher())
        self.assertEqual(result['status'],'supported')
        self.assertTrue(result['search_parsed'])
        self.assertTrue(result['detail_parsed'])
        class Captcha:
            def get(self,url):return {'body':'<html>Verify you are human</html>','url':url,'status':200}
        self.assertEqual(test_source(source,'Praktikum KI',Captcha())['status'],'unsupported')
        class BrokenDetail:
            def get(self,url):return {'body':search if '/jobs?' in url else '<html>not a job</html>','url':url,'status':200}
        self.assertEqual(test_source(source,'Praktikum KI',BrokenDetail())['status'],'error')

    def test_empty_page_is_not_proof_of_custom_source_support(self):
        class Empty:
            def get(self,url):return {'body':'<html>0 jobs</html>','url':url,'status':200}
        source={'kind':'regional','base':'https://example.test','name':'Unadapted'}
        result=test_source(source,'KI',Empty())
        self.assertNotEqual(result['status'],'supported')
        self.assertIsNone(result['detail_parsed'])

if __name__ == '__main__':
    unittest.main()
