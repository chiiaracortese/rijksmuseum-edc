"""Positive and negative tests for pre-check adaptation (stdlib unittest)."""
import unittest
import json
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

ROOT=Path(__file__).resolve().parents[1]
spec=spec_from_file_location('prechecks', ROOT/'src'/'run_prechecks.py')
mod=module_from_spec(spec);spec.loader.exec_module(mod)
CONF=json.loads((ROOT/'config'/'prechecks_rijksmuseum.json').read_text())
DATA=json.loads((ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json').read_text())

class PreCheckTests(unittest.TestCase):
    def test_actual_data_no_blocking_errors(self):
        r=mod.execute_checks(DATA,CONF,'data.json')
        self.assertEqual(r['summary']['blocking_findings'],0)
        self.assertEqual(r['summary']['review_findings'],0)

    def test_wrong_uri(self):
        a=json.loads(json.dumps(DATA[:1]));a[0]['object_uri']='non-un-URI'
        r=mod.execute_checks(a,CONF,'bad.json')
        self.assertGreater(r['summary']['blocking_findings'],0)
        self.assertIn('iri_http_syntax',[k['rule'] for k in r['rules'] if k['findings']])

    def test_duplicate_uri(self):
        a=json.loads(json.dumps(DATA[:2]));a[1]['object_uri']=a[0]['object_uri']
        r=mod.execute_checks(a,CONF,'bad.json')
        self.assertEqual(next(k['findings'] for k in r['rules'] if k['rule']=='unique_object_uri'),1)

    def test_inverted_years(self):
        a=json.loads(json.dumps(DATA[:1]));a[0]['production_dates']=[{
            'earliest_start':['2001-01-01T00:00:00Z'],
            'latest_end':['1901-12-31T23:59:59Z']}]
        r=mod.execute_checks(a,CONF,'bad.json')
        self.assertEqual(next(k['findings'] for k in r['rules'] if k['rule']=='production_year_order'),1)
        self.assertEqual(next(k['severity'] for k in r['rules'] if k['rule']=='production_year_order'),'review')
        self.assertEqual(r['summary']['blocking_findings'],0)
        self.assertEqual(r['summary']['review_findings'],1)
        self.assertEqual(r['summary']['decision'],'clean')

    def test_partial_date_is_informational(self):
        a=json.loads(json.dumps(DATA[:1]));a[0]['production_dates']=[{'earliest_start':['1857-01-01T00:00:00Z']}]
        r=mod.execute_checks(a,CONF,'partial.json')
        self.assertEqual(r['summary']['blocking_findings'],0)
        self.assertEqual(r['summary']['review_findings'],0)
        self.assertEqual(r['summary']['informational_findings'],1)

    def test_no_mutation(self):
        a=json.loads(json.dumps(DATA[:3])); before=json.dumps(a,ensure_ascii=False)
        mod.execute_checks(a,CONF,'data.json')
        self.assertEqual(json.dumps(a,ensure_ascii=False),before)

    def test_malformed_uri_in_nested_set(self):
        a=json.loads(json.dumps(DATA[:1]));a[0]['sets'][0]['uri']='http://bad host'
        r=mod.execute_checks(a,CONF,'bad.json')
        self.assertGreater(next(k['findings'] for k in r['rules'] if k['rule']=='iri_http_syntax'),0)

if __name__=='__main__':unittest.main()
