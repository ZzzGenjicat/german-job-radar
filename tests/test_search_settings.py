"""Search settings must drive the next query as one consistent transaction."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from radar.store import Store


class SearchSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'jobs.sqlite')
        self.sources = [
            {'id': 'ba', 'name': 'BA', 'base': 'https://www.arbeitsagentur.de', 'kind': 'ba'},
            {'id': 'regional', 'name': 'Regional', 'base': 'https://example.test', 'kind': 'regional'},
        ]
        self.store.ensure_v2_configuration(('Praktikum CRM', 'KI'), self.sources)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **changes):
        current = self.store.search_settings()
        value = {'revision': current['revision'], 'profile': current['profile'],
                 'keywords': [{'term': k['term'], 'enabled': k['enabled']} for k in current['keywords']],
                 'source_ids': [s['id'] for s in current['sources'] if s['enabled']],
                 'expansion_enabled': current['expansion_enabled']}
        return {**value, **changes}

    def test_one_save_changes_keywords_profile_sources_and_expansion(self):
        value = self.request(keywords=[{'term': 'HR', 'enabled': True}], source_ids=['regional'], expansion_enabled=False)
        value['profile'].update(role_types=['regular'], fulltime_required=False, exclusions=['Senior'])
        saved = self.store.search_settings(value)
        self.assertEqual([k['term'] for k in self.store.keywords()], ['HR'])
        self.assertEqual(self.store.profile()['role_types'], ['regular'])
        self.assertFalse(self.store.profile()['fulltime_required'])
        self.assertEqual([s['id'] for s in saved['sources'] if s['enabled']], ['regional'])
        self.assertFalse(self.store.expansion_settings()['enabled'])
        self.assertNotEqual(saved['revision'], value['revision'])
        self.assertEqual(saved, Store(self.store.path).search_settings())

    def test_invalid_part_does_not_partially_save_other_fields(self):
        before = self.store.search_settings()
        for invalid in ({'source_ids': []}, {'source_ids': ['unknown']}, {'keywords': []},
                        {'keywords': [{'term': 'HR', 'enabled': False}]},
                        {'keywords': [{'term': 'HR', 'enabled': True}, {'term': ' hr ', 'enabled': True}]}):
            with self.subTest(invalid=invalid):
                value = self.request(expansion_enabled=False, **invalid)
                value['profile']['notes'] = 'must not persist'
                with self.assertRaises(ValueError):
                    self.store.search_settings(value)
                self.assertEqual(self.store.search_settings(), before)

    def test_old_direction_terms_are_visible_search_terms_and_migrate_once(self):
        profile = self.store.profile()
        profile['themes'] = ['Praktikum HR', 'Praktikum CRM']
        self.store.profile(profile)
        current = self.store.search_settings()
        self.assertEqual(current['profile']['themes'], [])
        self.assertEqual([k['term'] for k in current['keywords']], ['Praktikum CRM', 'KI', 'Praktikum HR'])
        with self.store.connect() as db:
            backup = json.loads(db.execute("SELECT value FROM settings WHERE name='legacy_themes_v4'").fetchone()[0])
        self.assertEqual(backup, profile['themes'])
        self.store.search_settings(self.request(keywords=[{'term': 'HR', 'enabled': True}]))
        self.assertEqual([k['term'] for k in self.store.search_settings()['keywords']], ['HR'])

    def test_disabled_legacy_term_stays_disabled_on_migration(self):
        word = self.store.keywords()[0]
        self.store.update_keyword(word['id'], word['term'], False)
        self.store.profile({**self.store.profile(), 'themes': [word['term']]})
        current = self.store.search_settings()
        self.assertFalse(next(k for k in current['keywords'] if k['term'] == word['term'])['enabled'])

    def test_stale_settings_cannot_overwrite_a_new_keyword_or_toggle(self):
        old = self.request()
        self.store.put_keyword('Controlling')
        with self.assertRaisesRegex(ValueError, '已.*更新|已.*改变|重新'):
            self.store.search_settings(old)
        self.assertIn('Controlling', [k['term'] for k in self.store.keywords()])

    def test_removed_words_are_blocked_from_automatic_readdition(self):
        self.store.search_settings(self.request(keywords=[{'term': 'HR', 'enabled': True}]))
        self.assertIn('praktikum crm', self.store.expansion_settings()['blocked'])
        self.assertIn('ki', self.store.expansion_settings()['blocked'])

    def test_disallows_hidden_direction_filter_in_new_settings(self):
        value = self.request()
        value['profile']['themes'] = ['hidden']
        with self.assertRaises(ValueError):
            self.store.search_settings(value)

    def test_saved_settings_drive_real_scanner_queries_and_snapshot(self):
        import radar.scan as scan
        value = self.request(keywords=[{'term': 'Praktikum HR', 'enabled': True}],
                             source_ids=['regional'], expansion_enabled=False)
        value['profile'].update(role_types=['regular'], fulltime_required=False)
        saved = self.store.search_settings(value)
        fetched = []

        def fetch(url):
            fetched.append(url)
            return {'body': '', 'url': url, 'status': 200}

        with patch.object(scan, 'DB', self.store.path), patch.object(scan, 'DATA', self.store.path.parent), \
                patch.object(scan, 'SOURCES', self.sources), patch.object(scan, 'Fetcher') as factory, \
                patch.object(scan, 'parse_search', return_value={'parsed': True, 'items': [], 'has_more': False}):
            factory.return_value.get.side_effect = fetch
            result = scan.run_scan()
        self.assertEqual(result['status'], 'complete')
        from radar.sources import query_url
        self.assertEqual(fetched, [query_url(self.sources[1], 'HR', 0, fulltime_required=False)])
        from radar.core import now_utc
        snapshot = self.store.view(now_utc())['snapshot']
        self.assertEqual(snapshot['queries'][0]['keyword'], 'HR')
        self.assertEqual(snapshot['stats']['effective_queries'], ['HR'])
        self.assertEqual(snapshot['stats']['search_revision'], saved['revision'])
        self.assertEqual(snapshot['stats']['search_profile']['role_types'], ['regular'])

    def test_legacy_single_letter_topic_migrates_without_losing_history(self):
        self.store.profile({**self.store.profile(), 'themes': ['R']})
        self.assertIn('R', [word['term'] for word in self.store.search_settings()['keywords']])


class SearchQueryTests(unittest.TestCase):
    def terms(self, words, roles):
        from radar.config import effective_search_terms
        return effective_search_terms([{'term': t, 'enabled': True} for t in words], {'role_types': roles})

    def test_regular_selection_removes_old_internship_prefix(self):
        self.assertEqual(self.terms(['Praktikum HR', 'Intern Controlling'], ['regular']), ['HR', 'Controlling'])

    def test_types_control_queries_and_duplicates_are_removed(self):
        self.assertEqual(self.terms(['HR', 'Praktikum HR'], ['internship', 'werkstudent_fulltime']), ['Praktikum HR', 'Werkstudent HR'])

    def test_regular_and_internship_uses_broad_term_without_redundant_queries(self):
        self.assertEqual(self.terms(['Intern CRM', 'Praktikant im Personalwesen'], ['regular', 'internship']), ['CRM', 'im Personalwesen'])

    def test_role_word_without_a_topic_is_not_a_zero_length_query(self):
        self.assertEqual(self.terms(['Praktikum'], ['internship']), ['Praktikum'])


if __name__ == '__main__':
    unittest.main()
