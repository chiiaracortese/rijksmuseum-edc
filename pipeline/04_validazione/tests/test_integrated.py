"""Local integration checks, with test data copies only."""
import json
import tempfile
import unittest
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_pipeline import run

class IntegrationTest(unittest.TestCase):
    def test_full_original(self):
        inp=ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'
        before=inp.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            code,s=run(inp,ROOT/'schemas'/'schema_25_campi.json',
                       ROOT/'config'/'prechecks_rijksmuseum.json', Path(td))
            self.assertEqual(code,0)
            self.assertEqual(s['status'],'checks_passed')
            self.assertEqual(s['stage_results']['ingestion']['records'],951)
            self.assertEqual(s['stage_results']['validation']['total_errors'],0)
            self.assertEqual(s['stage_results']['prechecks']['blocking_findings'],0)
            self.assertTrue((Path(td)/'profiling.json').exists())
        self.assertEqual(inp.read_bytes(),before)

    def test_bad_input_is_blocked(self):
        src=ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'
        data=json.loads(src.read_text(encoding='utf-8'))[:3]
        data[0]['object_uri']='not an uri'
        data[1]['titles']=['wrong']
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/'bad.json'
            bad.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            code,s=run(bad,ROOT/'schemas'/'schema_25_campi.json',
                       ROOT/'config'/'prechecks_rijksmuseum.json',Path(td)/'reports')
            self.assertEqual(code,1)
            self.assertEqual(s['status'],'blocked')
            self.assertGreater(s['stage_results']['validation']['total_errors'],0)
            self.assertGreater(s['stage_results']['prechecks']['blocking_findings'],0)

    def test_unexpected_field_is_rejected(self):
        src=ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'
        data=json.loads(src.read_text(encoding='utf-8'))[:1]
        data[0]['unexpected_field']='dummy'
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'unexpected.json'
            inp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            code,s=run(inp,ROOT/'schemas'/'schema_25_campi.json',
                       ROOT/'config'/'prechecks_rijksmuseum.json',Path(td)/'reports')
            self.assertEqual(code,1)
            self.assertGreater(s['stage_results']['validation']['total_errors'],0)

    def test_inverted_year_warning_does_not_block(self):
        src=ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'
        data=json.loads(src.read_text(encoding='utf-8'))[:1]
        data[0]['production_dates']=[{'earliest_start':['1911-01-01T00:00:00Z'],
                                      'latest_end':['1910-12-31T23:59:59Z']}]
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'inverted.json'
            p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            code,s=run(p,ROOT/'schemas'/'schema_25_campi.json',
                       ROOT/'config'/'prechecks_rijksmuseum.json',Path(td)/'out')
            self.assertEqual(code,0,s)
            self.assertEqual(s['status'],'checks_passed')
            self.assertEqual(s['stage_results']['prechecks']['blocking_findings'],0)
            self.assertEqual(s['stage_results']['prechecks']['review_findings'],1)
            self.assertEqual(s['review_status'],'pending')

if __name__=='__main__': unittest.main()
