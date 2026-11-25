import itertools
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import genera_policy_fase9 as mod


def val_bool(node, claims):
    """Controlla la sola logica dichiarativa; NON simula il verificatore reale EDC."""
    if 'odrl:or' in node:
        return any(val_bool(c,claims) for c in node['odrl:or']['@list'])
    if 'odrl:and' in node:
        return all(val_bool(c,claims) for c in node['odrl:and']['@list'])
    k=node['odrl:leftOperand']['@id'].rsplit('/',1)[-1]
    expected=node['odrl:rightOperand']['@value']
    assert node['odrl:operator']['@id']=='odrl:eq'
    return bool(claims.get(k,False))==expected

class TestFase9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'documentazione/manifest_14_dataset.json').read_text())['entries']
        cls.cases=json.loads((ROOT/'input_fase8/casi_di_test.json').read_text())['tests']

    def test_01_tutti_14_asset_e_id(self):
        self.assertEqual(len(self.manifest),14)
        self.assertEqual(len({x['edc_asset_id_proposto'] for x in self.manifest}),14)
        for x in self.manifest:
            p=json.loads((ROOT/x['offerta_odrl']).read_text())
            target=p['odrl:permission'][0]['odrl:target']['@id']
            self.assertTrue(target.endswith('/'+x['edc_asset_id_proposto']))
            self.assertEqual(p['@type'],'odrl:Offer')
            self.assertEqual(p['odrl:permission'][0]['odrl:action']['@id'],'odrl:use')

    def test_02_logica_completa_otto_combinazioni(self):
        p=json.loads((ROOT/'policies_odrl/offer_dipinti_e_pitture.jsonld').read_text())
        expr=p['odrl:permission'][0]['odrl:constraint']
        self.assertEqual(list(expr.keys())[1],'odrl:or')
        self.assertEqual(len(expr['odrl:or']['@list']),2)
        self.assertIn('odrl:and',expr['odrl:or']['@list'][0])
        for r1,r2,r3 in itertools.product([False,True],repeat=3):
            values={mod.RKEY['R1']:r1,mod.RKEY['R2']:r2,mod.RKEY['R3']:r3}
            self.assertEqual(val_bool(expr,values),(r1 and r2) or r3)

    def test_03_15_casi_fase8(self):
        self.assertEqual(len(self.cases),15)
        exp=json.loads((ROOT/'policies_odrl/offer_dipinti_e_pitture.jsonld').read_text())['odrl:permission'][0]['odrl:constraint']
        for t in self.cases:
            # La scheda Fase 8 marca un prerequisito comune non valido in un test: rifiuto esplicito.
            d={mod.RKEY[k]:t[k] for k in ['R1','R2','R3']}
            result=(t.get('prerequisites_valid',True) and val_bool(exp,d))
            self.assertEqual(result,t['expected_allow'],t['case'])

    def test_04_congruenza_edc_e_alternativa(self):
        p=json.loads((ROOT/'edc_templates/policy_scenario_A_negoziazione.json').read_text())
        c=p['policy']['permission'][0]['constraint']
        self.assertIn('or',c)
        self.assertIn('and',c['or'][0])
        self.assertEqual([t['leftOperand'] for t in c['or'][0]['and']],[mod.RKEY['R1'],mod.RKEY['R2']])
        self.assertEqual(c['or'][1]['leftOperand'],mod.RKEY['R3'])
        for x in self.manifest:
            cd=json.loads((ROOT/x['contratto_edc_bozza']).read_text())
            self.assertEqual(cd['contractPolicyId'],p['@id'])
            self.assertEqual(cd['accessPolicyId'],'policy-catalogo-visibile')
            self.assertEqual(cd['assetsSelector'][0]['operandRight'],x['edc_asset_id_proposto'])

    def test_05_rdf_jsonld_locale_se_disponibile(self):
        try: from rdflib import Graph, URIRef
        except ImportError: self.skipTest('rdflib non installato (verifica RDF opzionale)')
        for x in self.manifest:
            p=json.loads((ROOT/x['offerta_odrl']).read_text())
            g=Graph()
            g.parse(data=json.dumps(p),format='json-ld')
            odrl='http://www.w3.org/ns/odrl/2/'
            self.assertIn((URIRef(p['@id']),URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'),URIRef(odrl+'Offer')),g)
            self.assertTrue(any(pred==URIRef(odrl+'or') for _,pred,_ in g))
            self.assertTrue(any(pred==URIRef(odrl+'and') for _,pred,_ in g))
        t=Graph()
        t.parse(str(ROOT/'documentazione/profilo_estensione_tesi.ttl'),format='turtle')
        self.assertGreater(len(t),0)

if __name__=='__main__': unittest.main(verbosity=2)
