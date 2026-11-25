#!/usr/bin/env python3
"""Fase 9: produce documenti ODRL e bozze EDC, senza installare o invocare EDC.

La logica usa tre esiti R1,R2,R3 calcolati dal futuro verificatore di attributi,
non tre booleani auto-dichiarati dal Consumer.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'https://example.org/tesi-dataspace-rijksmuseum/'  # identificatori dimostrativi, NON endpoint reali
EDC_NS = 'https://w3id.org/edc/v0.0.1/ns/'
ODRL_NS = 'http://www.w3.org/ns/odrl/2/'
RKEY = {
    'R1':'museumAccreditationValid',
    'R2':'culturalProjectAuthorizationValid',
    'R3':'heritageProtectionMandateValid',
}

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def odrl_atom(req):
    return {
        '@type':'odrl:Constraint',
        'odrl:leftOperand':{'@id': BASE+'terms/'+RKEY[req]},
        'odrl:operator':{'@id':'odrl:eq'},
        'odrl:rightOperand':{'@value': True, '@type':'xsd:boolean'}
    }

def logic_odrl():
    return {
      '@type':'odrl:LogicalConstraint',
      'odrl:or':{'@list':[
        {'@type':'odrl:LogicalConstraint', 'odrl:and':{'@list':[odrl_atom('R1'),odrl_atom('R2')]}},
        odrl_atom('R3')
      ]}
    }

def portable_policy(cat, asset_id):
    return {
        '@context': {'odrl':ODRL_NS, 'xsd':'http://www.w3.org/2001/XMLSchema#'},
        '@id':BASE+'policies/offer/'+cat,
        '@type':'odrl:Offer',
        'odrl:profile': {'@id':BASE+'profiles/access-conditions'},
        'odrl:permission':[{
          '@type':'odrl:Permission',
          'odrl:target': {'@id':BASE+'assets/'+asset_id},
          'odrl:assigner': {'@id':BASE+'participants/provider-locale'},
          'odrl:action':{'@id':'odrl:use'},
          'odrl:constraint':logic_odrl()
        }]
    }

def edc_atom(req):
    return {
       'leftOperand':RKEY[req],
       'operator':{'@id':'odrl:eq'},
       'rightOperand':'true'
    }

def edc_policydef(pid, condition=None):
    # La forma è in stile Sample policy-enforcement EDC. Richiede adattamento alla release adottata.
    return {
        '@context': {'@vocab': EDC_NS},
        '@type':'PolicyDefinition',
        '@id':pid,
        'policy': {
           '@context':'http://www.w3.org/ns/odrl.jsonld',
           '@type':'Set',
           'permission':[{'action':'use', **({'constraint':condition} if condition is not None else {})}],
           'prohibition':[],
           'obligation':[]
        }
    }

def edc_complex():
    return {'or':[{'and':[edc_atom('R1'),edc_atom('R2')]}, edc_atom('R3')]}

def edc_contract(cid, asset_id, policy_id):
    return {
       '@context':{'@vocab':EDC_NS},
       '@type':'ContractDefinition',
       '@id':cid,
       'accessPolicyId':'policy-catalogo-visibile',
       'contractPolicyId':policy_id,
       'assetsSelector':[
         {'@type':'Criterion','operandLeft':EDC_NS+'id','operator':'=','operandRight':asset_id}
       ]
    }

def build():
    spec=json.loads((ROOT/'input_fase8/specifica_scenario_A.json').read_text(encoding='utf-8'))
    assert spec['access_expression']=='(R1 AND R2) OR R3'
    cats=json.loads((ROOT/'input_fase8/riepilogo_fase7.json').read_text(encoding='utf-8'))['categorie']
    assert len(cats)==14
    manifest=[]
    for c in cats:
        cat=c['categoria']; aid='rijksmuseum_'+cat+'_25_campi'
        outfile='policies_odrl/offer_'+cat+'.jsonld'
        write(ROOT/outfile,portable_policy(cat,aid))
        cdname='edc_templates/contractdefinitions/contract_'+cat+'.json'
        write(ROOT/cdname,edc_contract('contract-scenario-a-'+cat,aid,'policy-scenario-a-negoziazione'))
        manifest.append({'categoria':cat,'edc_asset_id_proposto':aid, 'numero_oggetti_riportato_da_fase7':c['numero_oggetti_normalizzati'], 'offerta_odrl':outfile,'contratto_edc_bozza':cdname})
    write(ROOT/'edc_templates/policy_scenario_A_negoziazione.json',edc_policydef('policy-scenario-a-negoziazione',edc_complex()))
    write(ROOT/'edc_templates/policy_catalogo_visibile.json',edc_policydef('policy-catalogo-visibile'))
    write(ROOT/'edc_templates/alternative_dipinti/policy_R1_AND_R2.json',edc_policydef('policy-scenario-a-ramo-ordinario',{'and':[edc_atom('R1'), edc_atom('R2')]}))
    write(ROOT/'edc_templates/alternative_dipinti/policy_R3.json',edc_policydef('policy-scenario-a-ramo-alternativo',edc_atom('R3')))
    sample='rijksmuseum_dipinti_e_pitture_25_campi'
    write(ROOT/'edc_templates/alternative_dipinti/contract_R1_AND_R2.json',edc_contract('contract-ramo-ordinario-dipinti',sample,'policy-scenario-a-ramo-ordinario'))
    write(ROOT/'edc_templates/alternative_dipinti/contract_R3.json',edc_contract('contract-ramo-alternativo-dipinti',sample,'policy-scenario-a-ramo-alternativo'))
    write(ROOT/'documentazione/manifest_14_dataset.json',{'phase':9,'scope':'14 JSON normalizzati (non arricchimenti LLM)', 'odrl_model':'(R1 AND R2) OR R3', 'entries':manifest})
    contract={
      'versione':'fase9-v1',
      'tipologia':'SPECIFICA VALUTAZIONE, non credenziale e non JSON-LD ODRL',
      'source':'Fase 8 - Scenario A revisionato',
      'access_expression':'(R1 AND R2) OR R3',
      'consumer_authenticated_claim_required':True,
      'condition_leftoperands':{k:{'edc_leftoperand':RKEY[k], 'portable_uri':BASE+'terms/'+RKEY[k], 'must_be_computed_by':'verificatore Provider su attributi attendibili', 'claim_set':next(e['claims'] for e in spec['requirements'] if e['id']==k)} for k in RKEY},
      'shared_controls':[
         'subject_id attestazione coincide con identità Consumer autenticata',
         'issuer approvato per lo specifico tipo di attestazione',
         'valid_from <= istante_valutazione < valid_until',
         'attestazione attiva e non revocata',
         'integrità o attendibilità prova verificata da registro/sistema di identità',
         'asset richiesto incluso nello scope quando applicabile'
      ],
      'r2_additional':['project_id non vuoto','project_type in catalogazione, digitalizzazione, conservazione', 'approval_status=approved', 'subject_id R2 coincide con Consumer autenticato (e con R1 se richiesto)'],
      'r3_additional':['organization_type=public_authority','mandate_type=cultural_heritage_protection','mandate_status=active'],
      'fail_closed': True,
      'path_isolation':'Se un percorso completo è valido, prove non valide dell’altro percorso non impediscono l’accesso',
      'issuer_architecture':'rimandata alla configurazione EDC',
      'boolean_claim_warning':'MAI utilizzare valori true inviati liberamente dal Consumer come prova; calcolarli da fonti attendibili.'
    }
    write(ROOT/'documentazione/contratto_valutatori_R1_R2_R3.json',contract)
    return manifest

if __name__=='__main__':
    r=build()
    print('Create',len(r),'offerte ODRL,',len(r),'contract definitions EDC, 2 policy EDC, 2 alternative EDC')
