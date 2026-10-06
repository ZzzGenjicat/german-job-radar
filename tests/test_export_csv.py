import csv
import io
import unittest
from radar.export_csv import build_csv


class ExportCsvTests(unittest.TestCase):
    def test_formula_prefix_after_whitespace_is_escaped(self):
        for title in ('\t=1+1','\r@SUM(1,2)','  +1','\n-1'):
            rows=list(csv.reader(io.StringIO(build_csv([{'title':title,'classification':'review'}]).lstrip('\ufeff'))))
            self.assertTrue(rows[2][2].startswith("'"),repr(title))

    def test_exports_numbered_excel_safe_rows(self):
        text=build_csv([{'classification':'recommended','title':'=HYPERLINK("bad")','company':'ACME','location':'Berlin','posted':'2026-09-22','source':'BA','search_terms':['Praktikum KI'],'matches':[{'label':'AI','reason':'Agent'}],'reasons':[],'url':'https://example.test/job','apply_url':'https://example.test/apply'}])
        self.assertTrue(text.startswith('\ufeff'))
        rows=list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
        self.assertEqual(rows[0][0],'德国岗位雷达（只作为建议）')
        self.assertEqual(rows[2][0],'1')
        self.assertEqual(rows[2][1],'待人工筛查')
        self.assertTrue(rows[2][2].startswith("'="))


if __name__=='__main__':unittest.main()
