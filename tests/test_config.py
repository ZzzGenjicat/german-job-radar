import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from radar.config import DEFAULT_PROFILE, validate_profile
from radar.store import Store


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'jobs.sqlite')
        self.sources = [
            {'id': 'ba', 'name': 'Arbeitsagentur', 'base': 'https://www.arbeitsagentur.de', 'region': '德国全国', 'kind': 'ba'},
            {'id': 'berlin', 'name': 'berliner.jobs', 'base': 'https://www.berliner.jobs', 'region': 'Berlin', 'kind': 'regional'},
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_migration_is_idempotent(self):
        self.store.ensure_v2_configuration(('Praktikum KI', 'Praktikum CRM'), self.sources)
        self.store.ensure_v2_configuration(('Praktikum KI', 'Praktikum CRM'), self.sources)
        self.assertEqual(['Praktikum KI', 'Praktikum CRM'], [x['term'] for x in self.store.keywords()])
        self.assertEqual(['ba', 'berlin'], [x['id'] for x in self.store.source_settings()])

    def test_new_user_can_change_career_without_an_unseen_ai_filter(self):
        from radar.core import evaluate
        self.store.ensure_v2_configuration(('KI', 'CRM'), self.sources)
        self.store.put_keyword('Buchhaltung')
        for keyword in self.store.keywords():
            if keyword['term'] != 'Buchhaltung':
                self.store.update_keyword(keyword['id'], keyword['term'], False)
        job = {'title': 'Buchhalter', 'description': 'Vollzeit. Finanzbuchhaltung.',
               'employment': ['FULL_TIME'], 'posted': '2026-10-07',
               'original_posted': '2026-10-07', 'apply_status': 'verified',
               'search_terms': [k['term'] for k in self.store.keywords() if k['enabled']]}
        result = evaluate(job, datetime.fromisoformat('2026-10-07T17:00:00+02:00'),
                          profile=self.store.profile())
        self.assertEqual(result['classification'], 'recommended', result['reasons'])

    def test_reinitializing_preserves_a_users_explicit_theme_filter(self):
        self.store.ensure_v2_configuration(('KI', 'CRM'), self.sources)
        saved = {**self.store.profile(), 'themes': ['CRM'], 'notes': 'Customer operations'}
        self.store.profile(saved)
        self.store.ensure_v2_configuration(('KI', 'CRM'), self.sources)
        self.assertEqual(self.store.profile(), saved)

    def test_keyword_crud_normalizes_and_rejects_duplicates(self):
        self.store.ensure_v2_configuration(('Praktikum KI',), self.sources)
        created = self.store.put_keyword('  Intern AI Automation  ')
        self.assertEqual('Intern AI Automation', created['term'])
        with self.assertRaises(ValueError):
            self.store.put_keyword('intern ai automation')
        updated = self.store.update_keyword(created['id'], 'Intern CRM Automation', False)
        self.assertEqual((updated['term'], updated['enabled']), ('Intern CRM Automation', False))
        self.store.delete_keyword(created['id'])
        self.assertNotIn('Intern CRM Automation', [x['term'] for x in self.store.keywords()])

    def test_deleted_or_renamed_default_keyword_is_not_seeded_again(self):
        defaults=('Praktikum KI','Praktikum CRM')
        self.store.ensure_v2_configuration(defaults,self.sources)
        first,second=self.store.keywords()
        self.store.update_keyword(first['id'],'Praktikum Applied AI',True)
        self.store.delete_keyword(second['id'])
        self.store.ensure_v2_configuration(defaults,self.sources)
        self.assertEqual(['Praktikum Applied AI'],[x['term'] for x in self.store.keywords()])

    def test_profile_validation_is_closed_and_bounded(self):
        profile = validate_profile(DEFAULT_PROFILE)
        self.assertTrue(profile['fulltime_required'])
        with self.assertRaises(ValueError):
            validate_profile({**DEFAULT_PROFILE, 'unknown': True})
        with self.assertRaises(ValueError):
            validate_profile({**DEFAULT_PROFILE, 'notes': 'x' * 2001})

    def test_last_enabled_keyword_cannot_be_disabled(self):
        self.store.ensure_v2_configuration(('CRM',),self.sources)
        word=self.store.keywords()[0]
        with self.assertRaises(ValueError):
            self.store.update_keyword(word['id'],word['term'],False)

    def test_source_toggle_rejects_unknown_and_disabling_all(self):
        self.store.ensure_v2_configuration(('Praktikum KI',), self.sources)
        self.store.set_source_enabled('ba', False)
        with self.assertRaises(ValueError):
            self.store.set_source_enabled('missing', True)
        with self.assertRaises(ValueError):
            self.store.set_source_enabled('berlin', False)

    def test_cv_text_is_kept_out_of_sqlite_settings(self):
        metadata={'id':'cv1','original_name':'cv.pdf','stored_name':'abc.pdf','kind':'pdf','text':'SECRET CV TEXT','chars':14}
        self.store.set_cv(metadata)
        with self.store.connect() as db:
            raw=db.execute("SELECT value FROM settings WHERE name='current_cv'").fetchone()['value']
        self.assertNotIn('SECRET CV TEXT',raw)
        self.assertEqual(self.store.current_cv(include_text=True)['text'],'SECRET CV TEXT')
        self.store.clear_cv()
        self.assertIsNone(self.store.current_cv())


if __name__ == '__main__':
    unittest.main()
