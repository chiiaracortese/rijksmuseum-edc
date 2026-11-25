#!/usr/bin/env python3
"""Confronta i 14 JSON originali (26) con i rigenerati (25), in sola lettura.

Per ogni oggetto verifica:
  - stesse URI e ordine record;
  - 24 campi non coinvolti invariati;
  - nuove etichette production_techniques = tutte le vecchie etichette
    production_techniques + production_roles, senza perdite/aggiunte;
  - production_roles assente, e 25 campi esatti.

Si confrontano le etichette come multinsieme: i dati sorgente possono avere
un ordine d'origine diverso da quello delle liste prodotte dalla partizione.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path

from macrocategorie_core_14 import FILE_NAMES, FIELDS


def records(path: Path):
    """Iteratore JSON-array basato solo sulla libreria standard; non carica tutto il file."""
    decoder=json.JSONDecoder()
    with path.open('r',encoding='utf-8-sig') as fh:
        buff=''; p=0
        def require():
            nonlocal buff,p
            if p < len(buff): return True
            buff='';p=0
            chunk=fh.read(131072)
            if chunk:
                buff=chunk
                return True
            return False
        def peek():
            nonlocal p
            while require():
                if buff[p].isspace(): p+=1
                else:return buff[p]
            return None
        if peek() != '[':
            raise ValueError(f'{path}: JSON array expected')
        p+=1
        while True:
            c=peek()
            if c == ']':
                p+=1
                if peek() is not None: raise ValueError(f'{path}: trailing data')
                return
            if c is None:
                raise ValueError(f'{path}: unexpected EOF')
            while True:
                try:
                    obj,end=decoder.raw_decode(buff,p)
                    p=end
                    break
                except json.JSONDecodeError as e:
                    extra=fh.read(131072)
                    if not extra:raise ValueError(f'{path}: incomplete/invalid JSON: {e}') from e
                    buff+=extra
            if not isinstance(obj,dict):raise ValueError(f'{path}: non-object array element')
            yield obj
            c=peek()
            if c==',': p+=1
            elif c==']':continue
            else:raise ValueError(f'{path}: expected comma or close bracket')


def compare(original:Path,new:Path):
    expected_keys=set(FIELDS)
    count=0
    for n,(o,v) in enumerate(zip_longest(records(original),records(new)),1):
        if o is None or v is None:
            raise AssertionError(f'Record count differs at position {n}')
        if set(v)!=expected_keys:
            raise AssertionError(f'New schema keys not as expected, record {n}: {v.get("object_uri")}')
        if set(o)!=expected_keys|{'production_roles'}:
            raise AssertionError(f'Original schema keys unexpected, record {n}: {o.get("object_uri")}')
        if o.get('object_uri') != v.get('object_uri'):
            raise AssertionError(f'URI mismatch at position {n}')
        for key in FIELDS:
            if key=='production_techniques':continue
            if o[key]!=v[key]:
                raise AssertionError(f'Changed other field {key} at position {n}: {v.get("object_uri")}')
        source_tech=o['production_techniques']
        source_roles=o['production_roles']
        new_tech=v['production_techniques']
        if not all(isinstance(item,list) for item in [source_tech,source_roles,new_tech]):
            raise AssertionError(f'Non-list techniques/roles, record {n}')
        if Counter(source_tech+source_roles) != Counter(new_tech):
            raise AssertionError(f'Term loss/addition at position {n}: {v.get("object_uri")}')
        count=n
    return count


def main():
    parser=argparse.ArgumentParser(description='Check regenerated 25-field JSONs against old 26-field JSONs, read-only')
    parser.add_argument('--old-dir',type=Path,required=True,help='Folder containing all 14 26-field originals')
    parser.add_argument('--new-dir',type=Path,required=True,help='Folder containing new 25-field JSONs')
    parser.add_argument('--category',choices=sorted(FILE_NAMES),help='Check only one category')
    args=parser.parse_args()
    chosen=[args.category] if args.category else list(FILE_NAMES)
    failures=0
    for name in chosen:
        new_name=FILE_NAMES[name]
        old_name=new_name.replace('_25_campi.json','_26_campi.json')
        old_path=args.old_dir/old_name
        new_path=args.new_dir/new_name
        if not old_path.is_file() or not new_path.is_file():
            print(f'MISSING {name}: old={old_path.is_file()} new={new_path.is_file()}')
            failures+=1
            continue
        try:
            n=compare(old_path,new_path)
            print(f'OK {name}: {n:,} records; remaining fields unchanged; all terms retained')
        except (ValueError,AssertionError,TypeError) as e:
            failures+=1
            print(f'FAIL {name}: {e}')
    if failures:
        raise SystemExit(f'{failures} categories failed / unavailable. Do not replace originals.')
    print('CHECK PASSED for all selected categories. Still requires origin-RDF semantic interpretation.')

if __name__=='__main__':main()
