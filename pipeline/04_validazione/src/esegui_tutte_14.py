"""Execute local phases 1-3 on all available 25-field Rijksmuseum category JSON files.

No input is modified. No source-RDF relations are inferred.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from run_pipeline import run, save_json

CATEGORIES = (
    'fotografie', 'monete_medaglie', 'dipinti_e_pitture', 'sculture',
    'stampe', 'armi_oggetti_militari', 'gioielli_accessori',
    'strumenti_scientifici_musicali', 'oggetti_vetro',
    'ceramiche_porcellane', 'tessuti_abbigliamento', 'mobili_arredi',
    'libri_documenti', 'modelli_manufatti_tecnici',
)
ROOT=Path(__file__).resolve().parents[1]

def main(argv=None):
    ap=argparse.ArgumentParser(description='Rijksmuseum: verifica delle 14 macrocategorie, schema di 25 campi')
    ap.add_argument('--input-dir',required=True, help='Cartella con i 14 file JSON a 25 campi')
    ap.add_argument('--out-dir',default=str(ROOT/'reports'/'tutte_le_macrocategorie'))
    ap.add_argument('--schema',default=str(ROOT/'schemas'/'schema_25_campi.json'))
    ap.add_argument('--config',default=str(ROOT/'config'/'prechecks_rijksmuseum.json'))
    args=ap.parse_args(argv)
    input_dir=Path(args.input_dir).expanduser().resolve()
    out_dir=Path(args.out_dir).expanduser().resolve()
    if not input_dir.is_dir():
        ap.error('La cartella degli input non esiste')
    results=[]
    missing=[]
    for name in CATEGORIES:
        p=input_dir/f'rijksmuseum_{name}_25_campi.json'
        if not p.is_file():
            missing.append(name)
            print(f'MANCANTE: {p.name}')
            continue
        code, summary=run(p,args.schema,args.config,out_dir/name)
        stages=summary.get('stage_results',{})
        validation=stages.get('validation',{})
        pre=stages.get('prechecks',{})
        ingestion=stages.get('ingestion',{})
        results.append({
            'macrocategoria':name, 'file':str(p), 'status':summary['status'],
            'records':ingestion.get('records'),
            'schema_errors':validation.get('total_errors'),
            'blocking_prechecks':pre.get('blocking_findings'),
            'review_prechecks':pre.get('review_findings'),
            'informational_prechecks':pre.get('informational_findings'),
            'input_unchanged':summary.get('input_unchanged'),
            'return_code':code,
        })
        print(f"{name}: {summary['status']} | oggetti={ingestion.get('records')} | "
              f"schema={validation.get('total_errors')} | errori={pre.get('blocking_findings')} | revisioni={pre.get('review_findings')}")
    full=len(results)==len(CATEGORIES) and not missing
    failures=sum(r['status']!='checks_passed' for r in results)
    summary={
        'component':'Esecuzione cumulativa delle fasi 1–3, contratto JSON a 25 campi',
        'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'input_dir':str(input_dir),'output_dir':str(out_dir),
        'categories_expected':len(CATEGORIES),'categories_processed':len(results),
        'missing_categories':missing,'categories_blocked_or_errored':failures,
        'all_categories_checked':full,
        'review_findings_total':sum((r.get('review_prechecks') or 0) for r in results),
        'informational_findings_total':sum((r.get('informational_prechecks') or 0) for r in results),
        'quality_review_required':any(r.get('review_prechecks') for r in results),
        'status':'complete_checks_passed' if full and not failures else ('incomplete' if missing else 'attention_required'),
        'results':results,
        'note':'Controlli tecnici superati non equivalgono a certificazione storica o pubblicabilità. Le segnalazioni cronologiche rimangono nel report per revisione.'
    }
    save_json(out_dir/'riepilogo_14_macrocategorie.json',summary)
    print('Riepilogo:',out_dir/'riepilogo_14_macrocategorie.json')
    return 0 if full and failures==0 else (2 if not full else 1)

if __name__=='__main__':
    sys.exit(main())
