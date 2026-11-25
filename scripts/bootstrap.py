#!/usr/bin/env python3
"""Bootstrap locale del progetto Rijksmuseum EDC essenziale.
Registra un Data Plane condiviso e pubblica ciascun dataset con policy e contratto dedicati.
"""
from __future__ import annotations
import json, os, sys, time, socket
from uuid import uuid5, NAMESPACE_URL
from pathlib import Path
from edc_offer_guard import should_register_contract
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
P=os.getenv('EDC_PROVIDER_API_BASE','http://provider:19193/management/v4')
C=os.getenv('EDC_CONSUMER_API_BASE','http://consumer:29193/management/v4')
CONTEXT='https://w3id.org/edc/connector/management/v2'
VOCAB='https://w3id.org/edc/v0.0.1/ns/'


def read_properties(path):
    kv={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            a,b=line.split('=',1);kv[a.strip()]=b.strip()
    return kv

def call(base,path='',method='GET',payload=None,key=None,optional=False):
    blob=json.dumps(payload).encode('utf-8') if payload is not None else None
    headers={'Content-Type':'application/json','Accept':'application/json'}
    if key:headers['X-Api-Key']=key
    req=Request(base+path,headers=headers,data=blob,method=method)
    try:
        with urlopen(req,timeout=20) as response:
            raw=response.read()
            return json.loads(raw) if raw.strip() else None
    except HTTPError as exc:
        if optional and exc.code==404:return None
        # Never print secrets/authorization payloads or full server details.
        raise RuntimeError(f'HTTP {exc.code}: {method} {base.split("://")[-1].split("/")[0]}{path}') from None
    except URLError as exc:
        raise RuntimeError(f'Servizio non raggiungibile per {method} {path}: {exc.reason}') from None

def await_management(url,key):
    for attempt in range(45):
        try:
            call(url,'/dataplanes',key=key)
            return
        except (RuntimeError,ValueError):time.sleep(2)
    raise RuntimeError('API EDC non pronta: verifica i log in Docker Desktop')

def await_dataplane():
    for attempt in range(45):
        try:
            with socket.create_connection(('data-plane', 8181), timeout=2):
                return
        except OSError:
            time.sleep(2)
    raise RuntimeError('Data Plane non ancora pronto: vedere i log Docker')

def register_dataplane(base,key,identifier,endpoint,client_id,secret):
    current=call(base,'/dataplanes',key=key)
    if not isinstance(current,list):raise RuntimeError('Risposta dataplanes inattesa')
    if any(x.get('@id')==identifier for x in current):
        print('Data Plane già registrato:',identifier);return
    data={
      'dataplaneId':identifier,'endpoint':endpoint,'transferTypes':['HttpData-PULL'],
      'labels':[],
      'authorization':{
        'type':'oauth2_client_credentials',
        'tokenEndpoint':'http://auth-service:8080/oauth2/token',
        'clientId':client_id,'clientSecret':secret,
        'jwksUri':'http://auth-service:8080/oauth2/jwks'
      }
    }
    call(base,'/dataplanes',method='PUT',payload=data,key=key)
    print('Data Plane registrato:',identifier)

def register_cp(dataplane,cpid,endpoint,client_id,secret):
    data={
      'controlplaneId':cpid,'endpoint':endpoint,
      'authorization':{
        'type':'oauth2_client_credentials',
        'tokenEndpoint':'http://auth-service:8080/oauth2/token',
        'clientId':client_id,'clientSecret':secret,
        'jwksUri':'http://auth-service:8080/oauth2/jwks'
      }
    }
    call(f'http://{dataplane}:8181','/api/v1/controlplanes/',method='PUT',payload=data)
    print('Control Plane associato al Data Plane:',cpid)

def exists_resource(kind,ident,key):
    return call(P,'/'+kind+'/'+quote(ident,safe=''),key=key,optional=True)

def ensure_resource(kind,entity,key):
    ident=entity['@id']
    old=exists_resource(kind,ident,key)
    if old is not None:
        if old.get('@id')!=ident:raise RuntimeError(f'Risorsa non coerente: {ident}')
        # Verifica che la policy registrata sia coerente con quella prevista.
        if kind=='policydefinitions':
            def signature(data):
                return json.dumps(data.get('policy',{}).get('permission',[]),sort_keys=True)
            if signature(old)!=signature(entity):
                raise RuntimeError('Policy esistente diversa: '+ident+'; non sovrascrivo dati')
        if kind=='contractdefinitions':
            for field in ['accessPolicyId','contractPolicyId','assetsSelector']:
                if old.get(field)!=entity.get(field):
                    raise RuntimeError('ContractDefinition esistente non coerente: '+ident)
        return False
    call(P,'/'+kind,method='POST',payload=entity,key=key)
    if exists_resource(kind,ident,key) is None:raise RuntimeError('Creazione non confermata: '+ident)
    return True

def asset_definition(entry):
    return {
      '@context':{'@vocab':VOCAB},'@type':'Asset','@id':entry['asset_id'],
      'properties':{'name':'Rijksmuseum - '+entry['asset_id'], 'contenttype':'application/json',
                    'description':'Dataset Rijksmuseum: 10 opere normalizzate a 25 campi'},
      'dataAddress':{'type':'HttpData','baseUrl':'http://data-plane:8181/public/rijksmuseum/'+entry['asset_id']}
    }

def open_catalog_policy():
    return {
      '@context':[CONTEXT], '@type':'PolicyDefinition','@id':'policy-catalogo-rijk',
      'policy':{'@id':str(uuid5(NAMESPACE_URL,'rijk-catalog-open')), '@type':'Set','permission':[{'action':'use'}],
                'prohibition':[],'obligation':[]}
    }

def contract_policy(entry):
    asset=entry['asset_id']
    return {
      '@context':[CONTEXT], '@type':'PolicyDefinition',
      '@id':'policy-scenario-a-'+asset,
      'policy':{'@id':str(uuid5(NAMESPACE_URL,'rijk-'+asset)), '@type':'Set','permission':[{'action':'use','constraint':[
         {'or':[
           {'and':[
             {'leftOperand':'edc:museumAccreditationValid','operator':'eq','rightOperand':'true'},
             {'leftOperand':'edc:culturalProjectAuthorizationValid','operator':'eq','rightOperand':asset}]},
           {'leftOperand':'edc:heritageProtectionMandateValid','operator':'eq','rightOperand':asset}
         ]}
      ]}], 'prohibition':[],'obligation':[]}
    }

def contract_definition(entry):
    asset=entry['asset_id']
    return {
      '@context':[CONTEXT],'@type':'ContractDefinition','@id':'contract-scenario-a-'+asset,
      'accessPolicyId':'policy-catalogo-rijk',
      'contractPolicyId':'policy-scenario-a-'+asset,
      'assetsSelector':[{'@type':'Criterion','operandLeft':VOCAB+'id',
                         'operator':'=','operandRight':asset}]
    }

def main():
    provider=read_properties(ROOT/'edc/provider/config.properties')
    consumer=read_properties(ROOT/'edc/consumer/config.properties')
    kp=provider['web.http.management.auth.key']; kc=consumer['web.http.management.auth.key']
    found=json.loads((ROOT/'config/edc-assets.json').read_text(encoding='utf-8'))['assets']
    if not found:raise RuntimeError('Nessun asset nel registro')
    await_management(P,kp);await_management(C,kc);await_dataplane()
    # Uno stesso servizio Java riceve i segnali da due Control Plane distinti.
    register_cp('data-plane','provider','http://provider:19196/signaling',
                'rijksmuseum-provider-dataplane',os.environ['DATA_PLANE_OAUTH_CLIENT_SECRET'])
    register_cp('data-plane','consumer','http://consumer:29196/signaling',
                'rijksmuseum-consumer-dataplane',os.environ['CONSUMER_DATA_PLANE_OAUTH_CLIENT_SECRET'])
    register_dataplane(P,kp,'rijksmuseum-shared-dataplane',
                       'http://data-plane:8181/api/v1/dataflows',
                       'provider',os.environ['PROVIDER_OAUTH_CLIENT_SECRET'])
    register_dataplane(C,kc,'rijksmuseum-shared-dataplane',
                       'http://data-plane:8181/api/v1/dataflows',
                       'consumer',os.environ['CONSUMER_OAUTH_CLIENT_SECRET'])
    ensure_resource('policydefinitions',open_catalog_policy(),kp)
    created=0
    for entry in found:
        created+=int(ensure_resource('assets',asset_definition(entry),kp))
        ensure_resource('policydefinitions',contract_policy(entry),kp)
        if should_register_contract(ROOT, entry['asset_id']):
            ensure_resource('contractdefinitions',contract_definition(entry),kp)
        else:
            ident = 'contract-scenario-a-' + entry['asset_id']
            if exists_resource('contractdefinitions', ident, kp) is not None:
                raise RuntimeError('Offerta intenzionalmente revocata ma nuovamente presente in EDC: '
                                   + ident + '; riconciliare dal Provider, non ripubblico')
            print('Revoca rispettata dal bootstrap:', entry['asset_id'])
    print(f'Bootstrap terminato. Asset presenti: {len(found)}; asset creati ora: {created}')
    print('Nessuna negoziazione o trasferimento avviato dal bootstrap.')

if __name__=='__main__':
    try:main()
    except Exception as exc:sys.exit('ERRORE BOOTSTRAP: '+str(exc))
