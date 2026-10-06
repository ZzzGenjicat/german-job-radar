import unittest
from datetime import datetime
from radar.core import edition_for, evaluate, canonical_url, merge_jobs


def job(**changes):
    data = dict(title='Praktikum KI Automatisierung', company='Beispiel GmbH', location='Berlin',
                description='Freiwilliges Praktikum. Arbeitszeit: Vollzeit. Python und CRM Automatisierung.',
                employment=['INTERN', 'FULL_TIME'], posted='2026-09-21',
                original_posted='2026-09-21', valid_through='2026-10-30', source='bayern.jobs',
                url='https://www.bayern.jobs/job/beispiel-1234', apply_status='verified',
                apply_url='https://company.example/careers/1234', search_terms=['Praktikum KI'])
    data.update(changes)
    return data


class CalendarTests(unittest.TestCase):
    def test_before_and_after_18_berlin(self):
        self.assertEqual(edition_for(datetime.fromisoformat('2026-09-22T15:59:59+00:00')), '2026-09-21')
        self.assertEqual(edition_for(datetime.fromisoformat('2026-09-22T16:00:00+00:00')), '2026-09-22')

    def test_monday_and_weekend_do_not_invent_sunday_batch(self):
        self.assertEqual(edition_for(datetime.fromisoformat('2026-09-21T10:00:00+00:00')), '2026-09-18')
        self.assertEqual(edition_for(datetime.fromisoformat('2026-09-20T18:00:00+00:00')), '2026-09-18')

    def test_winter_uses_cet_not_fixed_utc_offset(self):
        self.assertEqual(edition_for(datetime.fromisoformat('2026-10-27T16:59:59+00:00')), '2026-10-26')
        self.assertEqual(edition_for(datetime.fromisoformat('2026-10-27T17:00:00+00:00')), '2026-10-27')


class EvidenceTests(unittest.TestCase):
    now = datetime.fromisoformat('2026-09-21T18:10:00+02:00')

    def check(self, **changes):
        return evaluate(job(**changes), self.now)

    def test_today_date_is_inside_window_but_has_no_invented_time(self):
        result = self.check()
        self.assertEqual(result['classification'], 'recommended')
        self.assertEqual(result['date_precision'], 'day')
        self.assertIn('2026-09-21', result['posted'])

    def test_yesterday_without_time_is_uncertain_24_hours(self):
        self.assertEqual(self.check(posted='2026-09-20')['classification'], 'review')

    def test_repost_does_not_become_new(self):
        result = self.check(original_posted='2026-08-17')
        self.assertEqual(result['classification'], 'excluded')
        self.assertTrue(any('日期' in x or '转载' in x for x in result['reasons']))

    def test_required_compulsory_internship_is_excluded(self):
        self.assertEqual(self.check(description='KI Python Vollzeit. Es muss ein Pflichtpraktikum sein.')['classification'], 'excluded')

    def test_optional_compulsory_or_voluntary_is_allowed(self):
        self.assertEqual(self.check(description='KI Python Vollzeit. Pflichtpraktikum oder freiwilliges Praktikum möglich.')['classification'], 'recommended')

    def test_unknown_voluntary_eligibility_needs_review(self):
        self.assertEqual(self.check(description='KI Python Vollzeit. Spannendes Praktikum.')['classification'], 'review')

    def test_working_student_fulltime_metadata_conflicts_with_20h(self):
        self.assertEqual(self.check(title='Werkstudent KI', description='Arbeitszeit: 20 Stunden pro Woche. KI Automatisierung.')['classification'], 'excluded')
        for wording in ('20 Wochenstunden','20 Std./Woche','Teilzeit, 25 Stunden pro Woche'):
            result=self.check(title='Werkstudent KI',description=f'{wording}. KI Automatisierung.',employment=['FULL_TIME'])
            self.assertEqual(result['classification'],'excluded',wording)

    def test_working_student_requires_fulltime_evidence(self):
        result=self.check(title='Werkstudent CRM',description='CRM und KI Automatisierung.',employment=[])
        self.assertEqual(result['classification'],'excluded')
        self.assertTrue(any('Werkstudent' in reason and 'Vollzeit' in reason for reason in result['reasons']))

    def test_working_student_accepts_fulltime_text_metadata_or_40_hours(self):
        base=dict(title='Werkstudent KI Automatisierung',original_posted='2026-09-21')
        self.assertNotEqual(self.check(**base,description='Vollzeit. KI Automatisierung.',employment=[])['classification'],'excluded')
        self.assertNotEqual(self.check(**base,description='KI Automatisierung.',employment=['FULL_TIME'])['classification'],'excluded')
        self.assertNotEqual(self.check(**base,description='40 Stunden pro Woche. KI Automatisierung.',employment=[])['classification'],'excluded')

    def test_no_pay_or_closed_application_never_recommended(self):
        self.assertEqual(self.check(description='KI Vollzeit freiwilliges Praktikum, unbezahlt.')['classification'], 'excluded')
        self.assertEqual(self.check(apply_status='closed')['classification'], 'excluded')
        self.assertEqual(self.check(apply_status='unverified')['classification'], 'review')

    def test_false_positive_ai_disclaimer_and_junior(self):
        self.assertEqual(self.check(title='Praktikum Pädagogik', description='Vollzeit freiwilliges Praktikum. Diese Anzeige wurde mit KI erstellt.')['classification'], 'excluded')
        self.assertEqual(self.check(title='Junior KI Engineer')['classification'], 'excluded')

    def test_future_date_and_expiry(self):
        self.assertEqual(self.check(posted='2026-09-23',original_posted='2026-09-23')['classification'], 'review')
        self.assertEqual(self.check(valid_through='2026-09-19')['classification'], 'excluded')

    def test_dedup_removes_tracking_preserves_job_identifier(self):
        self.assertEqual(canonical_url('https://jobs.example/position?id=45&utm_source=a#top'), 'https://jobs.example/position?id=45')
        rows = merge_jobs([job(), job(source='hessen.jobs', url='https://www.hessen.jobs/job/beispiel-999', search_terms=['Praktikum CRM'])])
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]['search_terms']), {'Praktikum KI','Praktikum CRM'})

    def test_ai_benefits_and_sales_alone_do_not_match(self):
        self.assertEqual(self.check(title='Praktikum Employer Branding',description='Vollzeit freiwilliges Praktikum. Recruiting organisieren. Wir fördern deine KI-Kompetenz durch interne Trainings.')['classification'],'excluded')
        self.assertEqual(self.check(title='Werkstudent Personalentwicklung Vertrieb',description='Vollzeit. Organisation von Seminaren für den Vertrieb.')['classification'],'excluded')

    def test_portal_date_and_fulltime_metadata_need_corroboration(self):
        self.assertEqual(self.check(original_posted=None)['classification'],'review')
        self.assertEqual(self.check(description='Freiwilliges Praktikum CRM Automatisierung.')['classification'],'review')

    def test_single_digit_original_date_is_old_not_unknown(self):
        self.assertEqual(self.check(original_posted='2025-9-24')['classification'],'excluded')

    def test_saved_profile_controls_role_types_and_exclusion_terms(self):
        profile={'role_types':['internship'],'fulltime_required':True,'locations':['Deutschland'],
                 'relocation':True,'themes':['AI'],'exclusions':['Rüstung'],'notes':''}
        student=evaluate(job(title='Werkstudent KI Automatisierung'),self.now,profile=profile)
        self.assertEqual(student['classification'],'excluded')
        self.assertTrue(any('求职目标' in reason for reason in student['reasons']))
        military=evaluate(job(description='Freiwilliges Praktikum. Vollzeit. KI Automatisierung in der Rüstungsindustrie.'),self.now,profile=profile)
        self.assertEqual(military['classification'],'excluded')
        self.assertTrue(any('Rüstung' in reason for reason in military['reasons']))

if __name__ == '__main__':
    unittest.main()
