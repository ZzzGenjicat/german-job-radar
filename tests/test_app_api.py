import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


class UiContractTests(unittest.TestCase):
    def test_removed_google_selection_and_confirmation_ui(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        for phrase in ('确认推荐','Google Drive 表格','查看并确认加入表格','selection-dialog'):
            self.assertNotIn(phrase,page)
        self.assertNotIn('/api/confirm',script)
        self.assertNotIn('data-select',script)

    def test_ui_delegates_external_links_to_backend(self):
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        self.assertIn('data-external-url',script)
        self.assertIn("post('/api/open-external'",script)

    def test_settings_ui_wires_profile_keywords_and_sources(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        for marker in ('settings-dialog','profile-form','keyword-form','source-settings'):
            self.assertIn(marker,page)
        for endpoint in ("'/api/profile'","'/api/keywords'","'/api/keywords/update'","'/api/keywords/delete'","'/api/sources/toggle'"):
            self.assertIn(endpoint,script)

    def test_openai_ui_never_requests_the_saved_key(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        self.assertIn('openai-key',page)
        self.assertIn("'/api/openai/credential'",script)
        self.assertIn("'/api/openai/delete'",script)
        self.assertNotIn('/api/openai/credential?show',script)

    def test_cv_ui_analyzes_a_draft_before_applying_keywords(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        for marker in ('cv-upload-form','cv-file','analyze-cv','ai-draft'):
            self.assertIn(marker,page)
        self.assertIn("'/api/cv/analyze'",script)
        self.assertIn("'/api/cv/apply-keywords'",script)

    def test_unsuitable_feedback_is_reviewed_before_acceptance(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        self.assertIn('feedback-dialog',page)
        self.assertIn('data-feedback',script)
        self.assertIn("'/api/feedback/analyze'",script)
        self.assertIn("'/api/feedback/accept'",script)
        self.assertLess(script.index("'/api/feedback/analyze'"),script.index("'/api/feedback/accept'"))

    def test_source_settings_support_testing_and_custom_urls(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        self.assertIn('custom-source-form',page)
        self.assertIn("'/api/sources/test'",script)
        self.assertIn("'/api/sources/custom'",script)

    def test_numbered_jobs_and_csv_export_are_wired(self):
        page=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        script=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
        self.assertIn('export-csv',page)
        self.assertIn("'/api/export.csv'",script)
        self.assertIn('job-number',script)
        self.assertIn('导出全部岗位',page)
        self.assertIn("fetch('/api/export.csv'",script)
        self.assertIn('JSON.stringify({})',script)


if __name__ == '__main__':
    unittest.main()
