# Copyright (C) 2025 SIB Swiss Institute of Bioinformatics: SPHN Connector
# Adaptation (C) 2026: Rijksmuseum thesis prototype.
# Derived in part from SPHN Connector / lib/pre_checks.py (RegexCheck,
# IRIValidationCheck). Distributed under GNU GPL v3 (see LICENSE.txt).
# NOT an SPHN official module. No personal/health records are processed here.
"""JSON pre-checks for Rijksmuseum (non-destructive, local, configuration driven).

The SPHN code searches patient data paths and uses rfc3987 for IRI validation.
This adaptation traverses JSON arrays by configured paths and validates absolute
HTTP(S) identifiers using urllib.parse. It checks only HTTP(S) URI syntax,
not full RFC3987 and not network resolvability.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def pointer(index, path):
    return f"/{index}/" + "/".join(str(s).replace('~','~0').replace('/','~1') for s in path)


def iter_field(record, selector):
    """Adapted from SPHN key-path traversal: handle list items explicitly.

    Selectors: object_uri, sets[].uri, equivalent_uris[].
    """
    bits = selector.split('.')
    items = [(record, ())]
    for bit in bits:
        array = bit.endswith('[]')
        key = bit[:-2] if array else bit
        out = []
        for obj, path in items:
            if not isinstance(obj, dict) or key not in obj:
                continue
            val = obj[key]
            if array:
                if isinstance(val, list):
                    out.extend((entry, path+(key,j)) for j,entry in enumerate(val))
            else:
                out.append((val, path+(key,)))
        items=out
    return items


def is_http_uri(value):
    """Purposefully narrower than SPHN's RFC3987 IRI check: HTTP(S) URLs only."""
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        z = urlsplit(value)
        if z.scheme not in {'http','https'} or not z.hostname or not z.netloc:
            return False
        if z.username is not None or z.password is not None:
            return False
        _ = z.port  # raises ValueError for malformed port
        if any(re.search(r'%(?![0-9a-fA-F]{2})', v) for v in (z.path,z.query,z.fragment)):
            return False
        return True
    except ValueError:
        return False


def year_of_datetime(value):
    # A minimum year-level check, not a historical calendar verifier.
    m=re.match(r'^(-?\d{4})-\d\d-\d\dT',value) if isinstance(value,str) else None
    return int(m.group(1)) if m else None


def execute_checks(data,config,input_path):
    """SPHN-style checks adapted to list[object]; extra rules for collection-level quality."""
    report={'tool':'Rijksmuseum pre-checks — selective SPHN adaptation',
            'source_code_origin':'SPHN Connector / lib/pre_checks.py: RegexCheck, IRIValidationCheck, path traversal',
            'rule_scope':'HTTP(S) URI syntax, configured regex, duplicate IDs; year-range order is non-blocking review',
            'input_file':str(input_path), 'records':len(data),
            'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'rules':[], 'summary':{}}
    maxex=config.get('max_examples_per_rule',12)
    def rec_rule(name,level,count,examples,examined,description):
        report['rules'].append({'rule':name,'severity':level,'checked_values':examined,
                 'findings':count,'examples':examples[:maxex],'description':description})
    if not isinstance(data,list):
        raise ValueError('Il file deve contenere un array JSON di oggetti')
    # Adaptation of IRIValidationCheck: configurable field paths instead of last key == iri.
    iri_bad=[]; iri_count=0
    for i,record in enumerate(data):
        for selector in config['iri_fields']:
            for value,loc in iter_field(record,selector):
                iri_count+=1
                if not is_http_uri(value):
                    iri_bad.append({'path':pointer(i,loc),'value':value})
    rec_rule('iri_http_syntax','error',len(iri_bad),iri_bad,iri_count,
             'Sintassi URL assoluti HTTP(S); non controlla esistenza remota o RFC 3987 completo')
    # Adaptation of SPHN RegexCheck: configurable exact-match patterns, no auto edits.
    for rule in config['regex_rules']:
        pattern=re.compile(rule['regex']); bad=[]; examined=0
        for i,record in enumerate(data):
            for value,loc in iter_field(record,rule['field']):
                examined+=1
                if not isinstance(value,str) or pattern.fullmatch(value) is None:
                    bad.append({'path':pointer(i,loc),'value':value})
        rec_rule('regex:'+rule['id'],'error',len(bad),bad,examined,
                 'Vincolo di forma più specifico del generico campo URI')
    # New Rijksmuseum collection-level check: duplicate object IDs.
    seen={};duplicate=[]
    for i,record in enumerate(data):
        value=record.get('object_uri') if isinstance(record,dict) else None
        if value:
            if value in seen:
                duplicate.append({'path':pointer(i,('object_uri',)), 'value':value,
                                  'first_index':seen[value]})
            else:seen[value]=i
    rec_rule('unique_object_uri','error',len(duplicate),duplicate,len(data),
             'Identificatore di ogni oggetto unico all’interno del file')
    # New museum-specific rule, not SPHN: check only clearly inverted YEAR ranges.
    inverted=[]; partial=[];date_windows=0; skipped=0; examined_dates=0
    for i,record in enumerate(data):
        for j,date in enumerate(record.get('production_dates',[]) if isinstance(record,dict) else []):
            if not isinstance(date,dict):continue
            examined_dates+=1
            if ('earliest_start' in date) != ('latest_end' in date):
                partial.append({'path':pointer(i,('production_dates',j)),
                                'missing_property':'latest_end' if 'latest_end' not in date else 'earliest_start'})
            start=date.get('earliest_start',[]);end=date.get('latest_end',[])
            a=[year_of_datetime(v) for v in start if isinstance(v,str)] if isinstance(start,list) else []
            b=[year_of_datetime(v) for v in end if isinstance(v,str)] if isinstance(end,list) else []
            a=[v for v in a if v is not None];b=[v for v in b if v is not None]
            if not a or not b:
                skipped+=1;continue
            date_windows+=1
            if min(a)>max(b):
                inverted.append({'path':pointer(i,('production_dates',j)),
                                 'start_years':a,'end_years':b})
    rec_rule('production_year_order','review',len(inverted),inverted,date_windows,
             'Intervalli con anno iniziale > anno finale: revisione informativa, senza correzione e senza blocco')
    rec_rule('production_date_partial','info',len(partial),partial,examined_dates,
             'Intervalli con un solo estremo: consentiti dallo schema, non imputati')
    report['summary']={
        'blocking_findings':sum(x['findings'] for x in report['rules'] if x['severity']=='error'),
        'review_findings':sum(x['findings'] for x in report['rules'] if x['severity']=='review'),
        'informational_findings':sum(x['findings'] for x in report['rules'] if x['severity']=='info'),
        'unparsed_or_missing_date_windows':skipped,
        'decision':'clean',
    }
    if report['summary']['blocking_findings']:
        report['summary']['decision']='blocked'
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description='Pre-check Rijksmuseum derivati in parte da SPHN')
    p.add_argument('input_json')
    p.add_argument('--config',default='config/prechecks_rijksmuseum.json')
    p.add_argument('--report',default='reports/prechecks_951_record.json')
    args=p.parse_args(argv)
    try:
        src=Path(args.input_json)
        before=hashlib.sha256(src.read_bytes()).hexdigest()
        data=json.loads(src.read_text(encoding='utf-8'))
        config=json.loads(Path(args.config).read_text(encoding='utf-8'))
        result=execute_checks(data,config,src)
        after=hashlib.sha256(src.read_bytes()).hexdigest()
        result['sha256_input_before_after']={'before':before,'after':after,'unchanged':before==after}
        dest=Path(args.report);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        s=result['summary']
        print(f"Record: {result['records']} | errori bloccanti: {s['blocking_findings']} | segnalazioni da rivedere: {s['review_findings']} | modifiche all'input: {not before==after}")
        return 1 if s['blocking_findings'] else 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f'Errore di esecuzione: {e}',file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
