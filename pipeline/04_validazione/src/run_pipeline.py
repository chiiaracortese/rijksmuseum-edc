# Rijksmuseum thesis prototype 2026: integration runner, not official SPHN Connector.
"""Local orchestration: profiling -> SPHN-derived JSON Schema -> pre-checks -> reports.

No input mutation; warnings do not become facts; no EDC, ODRL, rights clearance or RDF.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from profiling import profile_data
from validate_json import validate_data
from run_prechecks import execute_checks

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def save_json(path, data):
    p=Path(path);p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def run(input_file, schema_file, config_file, output_dir):
    input_file=Path(input_file).resolve()
    schema_file=Path(schema_file).resolve()
    config_file=Path(config_file).resolve()
    output_dir=Path(output_dir).resolve()
    output_dir.mkdir(parents=True,exist_ok=True)
    sha_before=digest(input_file)
    summary={
        'component':'Pipeline locale Rijksmuseum: fasi 0-3',
        'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'source_code':'schema validator adapted from SPHN; pre-check adaptation from SPHN; profiler and runner newly written',
        'inputs':{'json':str(input_file),'schema':str(schema_file),'prechecks_config':str(config_file)},
        'sha256':{'input_before':sha_before,'schema':digest(schema_file),'config':digest(config_file)},
        'stage_results':{},'status':'execution_error',
        'release_decision':'NOT_ASSESSED — l’assenza di errori non autorizza la pubblicazione',
    }
    try:
        data=json.loads(input_file.read_text(encoding='utf-8'))
        schema=json.loads(schema_file.read_text(encoding='utf-8'))
        config=json.loads(config_file.read_text(encoding='utf-8'))
        if not isinstance(data,list):raise ValueError('Il file input deve essere un array JSON')
        expected=schema['items']['required']
        summary['stage_results']['ingestion']={'status':'completed','records':len(data)}
        profile=profile_data(data,expected)
        save_json(output_dir/'profiling.json',profile)
        summary['stage_results']['profiling']={'status':'completed','fields_profiled':len(profile['field_stats'])}
        validation_report=output_dir/'validazione_schema.json'
        validation_exit=validate_data(str(schema_file),str(input_file),True,str(validation_report))
        validation=json.loads(validation_report.read_text(encoding='utf-8'))
        if validation_exit==2:
            raise RuntimeError('Validatore JSON Schema non eseguito correttamente: '+str(validation.get('execution_error')))
        summary['stage_results']['validation']={
            'status':'completed','total_errors':validation['total_validation_errors'],
            'invalid_records':validation['invalid_records'],
        }
        pre=execute_checks(data,config,input_file)
        save_json(output_dir/'prechecks.json',pre)
        summary['stage_results']['prechecks']={
            'status':'completed','blocking_findings':pre['summary']['blocking_findings'],
            'review_findings':pre['summary']['review_findings'],
            'informational_findings':pre['summary'].get('informational_findings',0)}
        sha_after=digest(input_file)
        summary['sha256']['input_after']=sha_after
        summary['input_unchanged']=(sha_before==sha_after)
        if not summary['input_unchanged']:
            summary['status']='execution_error'
            summary['message']='Input changed unexpectedly; investigate.'
            code=2
        elif validation['total_validation_errors'] or pre['summary']['blocking_findings']:
            summary['status']='blocked'
            summary['message']='Errori bloccanti: dati da correggere/verificare prima di procedere.'
            code=1
        else:
            summary['status']='checks_passed'
            summary['review_status']='pending' if pre['summary']['review_findings'] else 'none'
            summary['message']=('Controlli tecnici locali superati; anomalie cronologiche segnalate per revisione, senza correzione automatica. ' if pre['summary']['review_findings'] else 'Controlli tecnici locali superati. ') + 'Semantica RDF, licenze, governance e pubblicazione non valutate.'
            code=0
    except Exception as ex:
        summary['status']='execution_error'
        summary['execution_error']=f'{type(ex).__name__}: {ex}'
        code=2
    finally:
        save_json(output_dir/'riepilogo_pipeline.json',summary)
    return code,summary

def main():
    ap=argparse.ArgumentParser(description='Rijksmuseum: ingestion, profiling, validazione strutturale e pre-check')
    ap.add_argument('input_json',nargs='?',default=str(PROJECT_ROOT/'input'/'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'))
    ap.add_argument('--schema',default=str(PROJECT_ROOT/'schemas'/'schema_25_campi.json'))
    ap.add_argument('--config',default=str(PROJECT_ROOT/'config'/'prechecks_rijksmuseum.json'))
    ap.add_argument('--out',default=str(PROJECT_ROOT/'reports'/'ultimo_run'))
    args=ap.parse_args()
    code,result=run(args.input_json,args.schema,args.config,args.out)
    if result['status']=='execution_error':
        print('ERRORE ESECUZIONE:',result.get('execution_error',result.get('message','unknown')),file=sys.stderr)
    else:
        details=result['stage_results']
        print(f"Record: {details['ingestion']['records']}; campi: {details['profiling']['fields_profiled']}")
        print(f"Violazioni schema: {details['validation']['total_errors']}; errori pre-check: {details['prechecks']['blocking_findings']}; segnalazioni da revisionare: {details['prechecks']['review_findings']}")
        print(f"Stato: {result['status']} | Input invariato: {result.get('input_unchanged')}")
    print('Report:',(Path(args.out)/'riepilogo_pipeline.json').resolve())
    return code

if __name__=='__main__':
    sys.exit(main())
