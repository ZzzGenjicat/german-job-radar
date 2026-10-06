import tempfile
import unittest
from pathlib import Path
from radar.config import DEFAULT_PROFILE
from radar.store import Store


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'test.sqlite')
        self.store.ensure_v2_configuration(('KI',), [])
        self.store.profile({**DEFAULT_PROFILE, 'role_types': ['regular'], 'themes': ['AI']})
        self.jobs = [dict(key=str(i), title='AI Engineer', description='KI Systeme mit RAG und LLM. Agentic AI Workflows.', classification='review') for i in range(2)]

    def tearDown(self):
        self.tmp.cleanup()

    def expand(self, jobs=None, run='run1'):
        from radar.expansion import expand_keywords
        return expand_keywords(self.store, self.jobs if jobs is None else jobs, run)

    def test_expands_once_with_two_jd_evidence_and_next_scan_terms(self):
        result = self.expand()
        self.assertEqual(result['status'], 'complete')
        terms = [k['term'] for k in self.store.keywords()]
        self.assertIn('RAG', terms)
        self.assertIn('LLM', terms)
        self.assertLessEqual(len(result['added']), 10)
        rag = next(x for x in result['added'] if x['term'] == 'RAG')
        self.assertEqual(rag['job_keys'], ['0', '1'])
        self.assertTrue(rag['reason'])
        self.assertEqual(self.expand(run='run2')['run_id'], 'run1')
        self.assertEqual(terms, [k['term'] for k in self.store.keywords()])

    def test_excluded_and_single_job_do_not_count_as_two_documents(self):
        self.assertEqual(self.expand(self.jobs[:1])['status'], 'pending')
        self.assertEqual(self.expand([{**j, 'classification': 'excluded'} for j in self.jobs])['status'], 'pending')

    def test_unrelated_keywords_and_ai_benefits_are_not_added(self):
        jobs = [{**j, 'description': 'Vollzeit. KI Aufgaben. Deine Benefits: RAG Weiterbildung und LLM Trainings.'} for j in self.jobs]
        self.expand(jobs)
        self.assertNotIn('RAG', [k['term'] for k in self.store.keywords()])

    def test_standalone_internal_training_is_not_duty_evidence(self):
        self.store.profile({**DEFAULT_PROFILE,'role_types':['regular'],'themes':['CRM']})
        jobs=[{**j,'title':'CRM Specialist','description':'CRM Prozesse. Interne Trainings in RAG und LLM.'} for j in self.jobs]
        self.expand(jobs)
        self.assertNotIn('RAG',[k['term'] for k in self.store.keywords()])
        self.assertNotIn('LLM',[k['term'] for k in self.store.keywords()])

    def test_optout_preserves_user_terms(self):
        self.store.expansion_settings({'enabled': False})
        self.expand()
        self.assertEqual([k['term'] for k in self.store.keywords()], ['KI'])

    def test_deleted_and_renamed_terms_are_blocked_before_expansion(self):
        deleted = self.store.put_keyword('RAG')
        renamed = self.store.put_keyword('LLM')
        self.store.delete_keyword(deleted['id'])
        self.store.update_keyword(renamed['id'], 'Large Language Models', True)
        self.expand()
        self.assertNotIn('RAG', [k['term'] for k in self.store.keywords()])
        self.assertNotIn('LLM', [k['term'] for k in self.store.keywords()])

    def test_disabled_terms_are_not_reenabled(self):
        keyword = self.store.put_keyword('RAG', False)
        self.expand()
        self.assertFalse(next(k for k in self.store.keywords() if k['id'] == keyword['id'])['enabled'])

    def test_user_changes_during_scan_prevent_stale_expansion(self):
        profile = self.store.profile()
        seeds = self.store.keywords()
        self.store.put_keyword('Buchhaltung')
        from radar.expansion import expand_keywords
        result = expand_keywords(self.store, self.jobs, 'run1', profile=profile, keywords=seeds)
        self.assertEqual(result['status'], 'pending')
        self.assertNotIn('RAG', [k['term'] for k in self.store.keywords()])


if __name__ == '__main__':
    unittest.main()
