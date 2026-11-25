"""CLI didattica. Ogni comando corrisponde ad una sola fase comprensibile."""
import argparse
import json
import sys
from pathlib import Path
from .registro import leggi_asset
from .edc_api import ClientEDC, leggi_config_consumer
from .discovery import estrai_offerte, confronta
from . import negoziazione, trasferimento, verifica


def main(argv=None):
    parser = argparse.ArgumentParser(description='Rijksmuseum EDC Essenziale — discovery, negoziazione, trasferimento, audit')
    parser.add_argument('--progetto', default=Path('/project'), type=Path,
                        help='Percorso della radice di questo progetto EDC (all’interno del container: /project)')
    parser.add_argument('--api', default='http://consumer:29193/management/v4',
                        help='Management API del Consumer EDC su localhost')
    actions = parser.add_subparsers(dest='comando', required=True)
    actions.add_parser('registro', help='Elenca gli asset dal registro locale; nessuna API')
    actions.add_parser('catalogo', help='Discovery reale dal Provider tramite Consumer EDC')
    offerta = actions.add_parser('offerta', help='Verifica la presenza di una offerta EDC')
    offerta.add_argument('asset_id')
    neg = actions.add_parser('negozia', help='Crea una negoziazione EDC reale (richiede --conferma)')
    neg.add_argument('asset_id')
    neg.add_argument('--conferma', action='store_true')
    trans = actions.add_parser('trasferisci', help='Trasferisce SOLO con accordo autorizzato (richiede --conferma)')
    trans.add_argument('evidenza', type=Path, help='File neg-....json restituito dal comando negozia')
    trans.add_argument('--conferma', action='store_true')
    audit = actions.add_parser('verifica', help='Verifica file e ricevuta già trasferiti dal Consumer Data Plane')
    audit.add_argument('evidenza', type=Path, help='File transfer-....json restituito dal comando trasferisci')
    args = parser.parse_args(argv)

    progetto = args.progetto.expanduser().resolve()
    assets = leggi_asset(progetto)
    if args.comando == 'registro':
        print('REGISTRO LOCALE (non è una discovery EDC):')
        for item in assets.values():
            print(' -', item['asset_id'])
        print('Totale:', len(assets))
        return 0

    if args.comando in ('negozia', 'trasferisci') and not args.conferma:
        print('OPERAZIONE NON ESEGUITA: aggiungi --conferma per creare un processo EDC reale.')
        return 2

    # Le evidenze sono archiviate nella directory locale del progetto.
    base = Path(__file__).resolve().parents[1] / 'evidence/workflow'
    neg_dir = base / 'negoziazioni'
    trans_dir = base / 'trasferimenti'
    audit_dir = base / 'verifiche'

    if args.comando == 'verifica':
        path, result = verifica.esegui(args.evidenza, trans_dir, audit_dir, assets, progetto)
        print('ESITO:', result['stato'])
        print('Sei controlli:', sum(result['checks'].values()), '/ 6')
        print('SHA-256:', result['sha256_ricevuto'])
        print('File ricevuto:', result['file_relativo'])
        print('Evidenza audit:', path)
        return 0 if result['stato'] == 'TRANSFER_VERIFIED' else 1

    config = leggi_config_consumer(progetto)
    api = ClientEDC(args.api, config['chiave'])
    if args.comando in ('catalogo', 'offerta'):
        offerte = estrai_offerte(api.richiesta_catalogo())
        righe = confronta(assets, offerte)
        if args.comando == 'catalogo':
            print('CATALOGO REALE EDC:')
            for r in righe:
                print(' -', r['asset_id'], '|', 'OFFERTA' if r['numero_offerte'] else 'NON TROVATO')
            print('Asset annunciati dal Provider:', len(offerte))
            print('Offerte per asset previsto:', sum(bool(r['numero_offerte']) for r in righe))
        else:
            if args.asset_id not in assets:
                raise ValueError('Asset sconosciuto nel registro locale')
            print(json.dumps(next(r for r in righe if r['asset_id'] == args.asset_id),
                             ensure_ascii=False, indent=2))
        print('Nessuna negoziazione né trasferimento avviati.')
        return 0

    print('Identità dichiarata nella configurazione Consumer:', config['identita'])
    print('AVVISO: Essenziale non cambia le identità e non riavvia Docker. La configurazione deve corrispondere al runtime attivo.')
    if args.comando == 'negozia':
        if args.asset_id not in assets:
            raise ValueError('Asset non previsto nel registro locale')
        path, result = negoziazione.esegui(api, args.asset_id, config['identita'], neg_dir)
        print('NEGOTIATION ID:', result['negotiation_id'])
        print('STATO EDC:', result['final_state'])
        print('ESITO:', result['outcome'])
        print('AGREEMENT:', result['agreement_id'] or 'ASSENTE')
        print('EVIDENZA:', path)
        if result['outcome'] == 'DENIED_BY_POLICY':
            print('Trasferimento NON avviato: rifiuto della policy.')
            return 0
        return 0 if result['outcome'] == 'AUTHORIZED' else 1

    if args.comando == 'trasferisci':
        path, result = trasferimento.esegui(api, args.evidenza, config['identita'], assets,
                                            neg_dir, trans_dir)
        print('TRANSFER PROCESS ID:', result['transfer_process_id'])
        print('STATO EDC:', result['last_state'])
        print('EVIDENZA:', path)
        print('L’avvio NON prova la ricezione: esegui il comando verifica.')
        return 0
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print('ERRORE:', exc, file=sys.stderr)
        sys.exit(1)
