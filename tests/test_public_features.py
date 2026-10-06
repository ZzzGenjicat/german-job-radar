import copy
import csv
import io
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import app
from radar.config import DEFAULT_PROFILE, validate_profile
from radar.core import evaluate
from radar.export_csv import build_csv
from radar.sources import query_url


class PublicFeaturesTests(unittest.TestCase):
    now = datetime.fromisoformat('2026-10-06T18:10:00+02:00')

    def profile(self, **values):
        return {**copy.deepcopy(DEFAULT_PROFILE), 'role_types': ['regular'],
                'themes': ['Buchhaltung'], 'exclusions': [], **values}

    def job(self, **values):
        return {'title': 'Junior Buchhalter', 'company': 'Example GmbH', 'location': 'Berlin',
                'description': 'Vollzeit. Finanzbuchhaltung und Rechnungsprüfung.',
                'employment': ['FULL_TIME'], 'posted': '2026-10-06',
                'original_posted': '2026-10-06', 'apply_status': 'verified',
                'search_terms': ['Buchhaltung'], 'url': 'https://example.test/job/1', **values}

    def test_regular_jobs_match_user_themes_without_inventing_cv_skills(self):
        profile = validate_profile(self.profile())
        result = evaluate(self.job(), self.now, profile=profile)
        self.assertEqual(result['classification'], 'recommended')
        self.assertEqual(result['role_type'], '正式岗位')
        self.assertTrue(result['matches'])
        self.assertTrue(all('你的' not in m['reason'] for m in result['matches']))

    def test_explicit_junior_exclusion_still_works(self):
        result = evaluate(self.job(), self.now, profile=self.profile(exclusions=['Junior']))
        self.assertEqual(result['classification'], 'excluded')

    def test_regular_only_still_rejects_internship(self):
        result = evaluate(self.job(title='Praktikum Buchhaltung'), self.now, profile=self.profile())
        self.assertEqual(result['classification'], 'excluded')

    def test_parttime_option_and_working_student_hours(self):
        job = self.job(title='Werkstudent Buchhaltung', description='20 Stunden pro Woche. Buchhaltung.', employment=['PART_TIME'])
        parttime = self.profile(role_types=['werkstudent_fulltime'], fulltime_required=False)
        self.assertEqual(evaluate(job, self.now, profile=parttime)['classification'], 'recommended')
        fulltime = {**parttime, 'fulltime_required': True}
        self.assertEqual(evaluate(job, self.now, profile=fulltime)['classification'], 'excluded')

    def test_no_themes_means_no_artificial_ai_filter(self):
        profile = validate_profile(self.profile(themes=[]))
        self.assertEqual(evaluate(self.job(title='Produktionsmitarbeiter', description='Vollzeit. Bedienung der Anlage.'), self.now, profile=profile)['classification'], 'recommended')

    def test_scanner_role_gate_and_optional_ba_fulltime_filter(self):
        from radar.config import role_allowed
        self.assertTrue(role_allowed('Junior Buchhalter', self.profile()))
        self.assertFalse(role_allowed('Praktikum Buchhaltung', self.profile()))
        params = parse_qs(urlsplit(query_url({'kind': 'ba', 'base': 'https://www.arbeitsagentur.de'}, 'Buchhaltung', fulltime_required=False)).query)
        self.assertNotIn('arbeitszeit', params)

    def test_two_lists_include_previous_and_keep_stable_csv_numbers(self):
        from radar.presentation import numbered_jobs, display_group
        jobs = numbered_jobs([{'classification': c, 'title': c, 'key': c} for c in ('recommended', 'review', 'previous', 'excluded')])
        self.assertEqual([display_group(j['classification']) for j in jobs], ['review'] * 3 + ['excluded'])
        rows = list(csv.reader(io.StringIO(build_csv(jobs).lstrip('\ufeff'))))
        self.assertEqual([r[0] for r in rows[2:]], ['1', '2', '3', '4'])
        self.assertEqual([r[1] for r in rows[2:]], ['待人工筛查'] * 3 + ['已排除'])
        self.assertIn('核验状态', rows[1])

    def test_custom_source_needs_name_and_url_only(self):
        with patch.object(app, 'validate_external_url', lambda value: value):
            source = app.custom_source({'name': 'Example Jobs', 'url': 'https://example.test/'})
        self.assertEqual(source['base'], 'https://example.test')
        self.assertNotIn('region', source)

    def test_ui_has_two_lists_regular_option_and_no_custom_region(self):
        page = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('data-view="recommended"', page)
        self.assertIn('待人工筛查', page)
        self.assertIn('role-regular', page)
        self.assertNotIn('custom-source-region', page)


if __name__ == '__main__':
    unittest.main()
