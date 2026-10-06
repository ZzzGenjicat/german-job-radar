import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from radar.feedback import apply_learned_rules, validate_rule
from radar.core import evaluate
from radar.store import Store


RULE={'title':'排除纯电话销售','scope':['sales'],'negative_any':['cold calling','telefonakquise'],
      'keep_if_any':['crm','automation','automatisierung','ki','ai'],'hard_exclude_any':[],
      'confidence':0.91,'explanation':'销售职责必须同时包含CRM、AI或自动化。'}


def job(description):
    return {'title':'Praktikum Vertrieb','company':'Example','location':'Berlin','description':description,
            'employment':['INTERN','FULL_TIME'],'posted':'2026-09-21','original_posted':'2026-09-21',
            'valid_through':'2026-10-30','source':'berliner.jobs','url':'https://jobs.example/1',
            'apply_status':'verified','apply_url':'https://jobs.example/apply/1','search_terms':['Praktikum Vertrieb KI']}


class FeedbackTests(unittest.TestCase):
    def test_rule_excludes_only_matching_sales_without_keep_signal(self):
        rule={'id':'r1',**validate_rule(RULE)}
        hit=apply_learned_rules(job('Vollzeit freiwilliges Praktikum. Cold calling und Telefonakquise im Vertrieb.'),[rule])
        self.assertEqual(hit[0]['id'],'r1')
        kept=apply_learned_rules(job('Vollzeit freiwilliges Praktikum. Cold calling mit CRM Automation und KI.'),[rule])
        self.assertEqual(kept,[])
        email=apply_learned_rules(job('Vollzeit freiwilliges Praktikum. Cold calling und E-Mail Outreach im Vertrieb.'),[rule])
        self.assertEqual(email[0]['id'],'r1')
        unrelated=apply_learned_rules({**job('Vollzeit freiwilliges Praktikum. Python Datenanalyse.'),'title':'Praktikum Data'},[rule])
        self.assertEqual(unrelated,[])

    def test_evaluate_identifies_learned_rule_in_evidence(self):
        result=evaluate(job('Vollzeit freiwilliges Praktikum. Cold calling, Telefonakquise und Digitalisierung der Vertriebsprozesse.'),datetime.fromisoformat('2026-09-21T18:10:00+02:00'),[{'id':'r1',**RULE}])
        self.assertEqual(result['classification'],'excluded')
        self.assertTrue(any('排除纯电话销售' in x for x in result['reasons']))

    def test_store_can_pause_update_and_delete_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite')
            saved=store.add_learned_rule(RULE,'job-1')
            self.assertTrue(saved['enabled'])
            paused=store.update_learned_rule(saved['id'],RULE,False)
            self.assertFalse(paused['enabled'])
            store.delete_learned_rule(saved['id'])
            self.assertEqual(store.learned_rules(),[])

    def test_pausing_rule_restores_job_from_saved_scan(self):
        now=datetime.fromisoformat('2026-09-21T18:10:00+02:00')
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite')
            saved=store.add_learned_rule(RULE,'job-1')
            run=store.start(now,'manual')
            evaluated=evaluate(job('Vollzeit freiwilliges Praktikum. Cold calling und Telefonakquise; Digitalisierung der Vertriebsprozesse.'),now,[{'id':saved['id'],**RULE}])
            store.finish(run,now,'complete',[evaluated],[],{})
            self.assertEqual(store.view(now)['snapshot']['jobs'][0]['classification'],'excluded')
            store.update_learned_rule(saved['id'],RULE,False)
            self.assertEqual(store.view(now)['snapshot']['jobs'][0]['classification'],'recommended')


if __name__=='__main__':unittest.main()
