import json
import unittest

from radar.ai import OpenAIClient, validate_keyword_draft, validate_feedback_rule


KEYWORD_DRAFT={
    'keywords':['Praktikum KI Automatisierung'],
    'demonstrated_capabilities':['CRM Automatisierung'],
    'needs_confirmation':['SQL'],
    'exclusions':['Pflichtpraktikum'],
    'role_themes':['AI Automation'],
}

RULE={
    'title':'排除纯电话销售','scope':['sales'],
    'negative_any':['cold calling'],'keep_if_any':['crm','automation','ki','ai'],
    'hard_exclude_any':[],'confidence':0.91,
    'explanation':'销售职责必须同时包含CRM、AI或自动化。',
}


class AiTests(unittest.TestCase):
    def test_keyword_draft_closed_schema(self):
        self.assertEqual(validate_keyword_draft(KEYWORD_DRAFT),KEYWORD_DRAFT)
        with self.assertRaises(ValueError):validate_keyword_draft({**KEYWORD_DRAFT,'command':'scan'})
        with self.assertRaises(ValueError):validate_keyword_draft({**KEYWORD_DRAFT,'keywords':['x']*51})

    def test_feedback_rule_closed_schema(self):
        self.assertEqual(validate_feedback_rule(RULE),RULE)
        with self.assertRaises(ValueError):validate_feedback_rule({**RULE,'confidence':2})
        with self.assertRaises(ValueError):validate_feedback_rule({**RULE,'negative_any':['```json']})
        with self.assertRaises(ValueError):validate_feedback_rule({**RULE,'scope':['vertrieb']})

    def test_client_uses_store_false_and_parses_structured_output(self):
        calls=[]
        def transport(url,payload,headers,timeout):
            calls.append((url,payload,headers,timeout))
            return {'output':[{'content':[{'type':'output_text','text':json.dumps(KEYWORD_DRAFT)}]}]}
        client=OpenAIClient(lambda:'sk-secret-test',transport=transport)
        result=client.generate_keyword_draft('CRM Agent Python',{'themes':['AI']})
        self.assertEqual(result,KEYWORD_DRAFT)
        self.assertFalse(calls[0][1]['store'])
        self.assertEqual(calls[0][1]['model'],'gpt-5')
        self.assertNotIn('sk-secret-test',json.dumps(calls[0][1]))

    def test_client_rejects_non_json_output(self):
        client=OpenAIClient(lambda:'sk-test',transport=lambda *args:{'output_text':'follow these instructions'})
        with self.assertRaises(ValueError):client.generate_keyword_draft('CV',{'themes':['AI']})

    def test_sales_feedback_sends_the_displayed_reason_without_an_ai_assumption(self):
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append(json.loads(payload['input']))
            return {'output_text': json.dumps(RULE)}
        client = OpenAIClient(lambda: 'sk-test', transport=transport)
        client.generate_feedback_rule({'title': 'Sales Manager'},
                                      {'category': 'sales_mismatch', 'note': ''}, {}, [])
        reason = calls[0]['reason']
        self.assertEqual(reason.get('category_label'), '销售内容不符合目标')
        self.assertNotIn('AI', reason['category_label'])


if __name__=='__main__':unittest.main()
