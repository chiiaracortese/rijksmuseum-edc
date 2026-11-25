"""Gestione strettamente circoscritta delle Contract Definition gia' registrate.

- Solo 14 asset del registro approvato
- Solo revoca/ripubblicazione di una Contract Definition con selector ID esatto
- Nessun endpoint per aggiungere asset, policy o modificare le definizioni
- Backup locale dell'intera risorsa prima della DELETE EDC
- Approva esplicitamente con ticket monouso, legato alla sessione e a una password

Le scritture EDC avvengono SOLO tramite commit confermato nel Provider locale.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from provider_readonly import management_config, fetch_query, simple_id

NS = 'https://w3id.org/edc/v0.0.1/ns/'
MANAGEMENT_CONTEXT = 'https://w3id.org/edc/connector/management/v2'
DIRNAME = '.provider-offer-archives'
CONFIRM_WORD = {'revoke': 'REVOCA', 'restore': 'RIPUBBLICA'}
TICKETS: dict[str, dict] = {}
TICKET_TTL = 120


class OfferError(ValueError):
    pass


def _current_utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _jsonbytes(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _digest(data):
    return hashlib.sha256(_jsonbytes(data)).hexdigest()


def _field(obj, key):
    if not isinstance(obj, dict):
        return None
    for name in (key, 'edc:' + key, NS + key):
        if name in obj:
            return obj[name]
    return None


def _selector_asset(selector):
    """Accetta solo un singolo criterio id = ASSET_ID, mai wildcard/OR/filtri ampi."""
    if isinstance(selector, list):
        if len(selector) != 1:
            return None
        selector = selector[0]
    if not isinstance(selector, dict):
        return None
    allowed = {'@type', '@context'} | {prefix + k for prefix in ('', 'edc:', NS)
                                          for k in ('operandLeft','operandRight','operator')}
    if set(selector) - allowed:
        return None
    left, right, operator = (_field(selector, 'operandLeft'),
                              _field(selector, 'operandRight'),
                              _field(selector, 'operator'))
    if left not in ('id', NS + 'id') or operator not in ('=', 'eq', 'EQ'):
        return None
    if not isinstance(right, str) or not re.fullmatch(r'rijksmuseum-[a-z0-9-]{1,150}', right):
        return None
    return right


def _api(config, method, path, body=None):
    # Qualsiasi URL viene costruito esclusivamente a partire dalla configurazione
    # loopback del Provider e da un ID quotato: mai da URL forniti dal browser.
    headers = {'X-Api-Key': config['key'], 'Accept': 'application/json'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(config['base'] + '/v4/contractdefinitions' + path,
                  data=(_jsonbytes(body) if body is not None else None),
                  method=method, headers=headers)
    try:
        with urlopen(req, timeout=7) as response:
            raw = response.read(256_000)
            if method == 'GET':
                try:
                    return json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise OfferError('Risposta EDC non leggibile; stato non confermato.')
            return response.status
    except HTTPError as exc:
        if exc.code == 404 and method == 'GET':
            return None
        raise OfferError(f'EDC ha restituito HTTP {exc.code}; verificare lo stato prima di ripetere.')
    except (URLError, TimeoutError, OSError):
        raise OfferError('Management API non raggiungibile; stato non confermato. Aggiornare i dati prima di ripetere.')


def _get_definition(config, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', ident):
        raise OfferError('Identificativo Contract Definition non sicuro.')
    return _api(config, 'GET', '/' + quote(ident, safe=''))


def _definitions(config):
    items, error = fetch_query(config, 'contractdefinitions')
    if items is None or error:
        raise OfferError('Elenco delle Contract Definition non completo: ' + str(error))
    return items


def _policies_and_assets(config):
    p, perr = fetch_query(config, 'policydefinitions')
    a, aerr = fetch_query(config, 'assets')
    if p is None or a is None or perr or aerr:
        raise OfferError('Impossibile verificare asset e policy EDC senza risposte complete.')
    return {str(simple_id(x)) for x in p}, {str(simple_id(x)) for x in a}


def _normalize_definition(record):
    # Non ricostruire silenziosamente Contract Definition con campi estesi.
    # Qualsiasi campo non riconosciuto blocca la revoca, preservando il record.
    ordinary = ('accessPolicyId', 'contractPolicyId', 'assetsSelector',
                'createdAt', 'updatedAt', 'participantContextId')
    allowed = {'@id', '@type', '@context', 'id'} | {
        pref + key for pref in ('', 'edc:', NS) for key in ordinary}
    if not isinstance(record, dict) or set(record) - allowed:
        raise OfferError('Contract Definition con campi aggiuntivi non gestiti: modifica bloccata.')
    ident = simple_id(record)
    access = _field(record, 'accessPolicyId')
    contract = _field(record, 'contractPolicyId')
    selector = _field(record, 'assetsSelector')
    if not all(isinstance(x, str) and x for x in (ident, access, contract)):
        raise OfferError('La definizione EDC non espone ID e riferimenti alle policy validi.')
    asset = _selector_asset(selector)
    if not asset:
        raise OfferError('Selector EDC non limitato a un unico Asset ID: operazione bloccata.')
    payload = {'@context': {'edc': NS}, '@type': 'edc:ContractDefinition',
               '@id': str(ident), 'edc:accessPolicyId': access,
               'edc:contractPolicyId': contract,
               'edc:assetsSelector': [
                   {'@type': 'edc:Criterion', 'edc:operandLeft': 'id',
                    'edc:operator': '=', 'edc:operandRight': asset}]}
    return {'asset_id': asset, 'definition_id': str(ident),
            'access_policy': access, 'contract_policy': contract,
            'payload': payload}


def _bootstrap_compatible_creation(meta):
    """Ricrea SOLO la stessa Contract Definition con lo schema già usato
    da scripts/bootstrap.py nel progetto attuale. Niente nuovi asset o policy.

    L'archivio mantiene la firma del contenuto semantico approvato; questo
    documento di trasporto rispetta la stessa serializzazione del bootstrap.
    """
    asset = meta['asset_id']
    if meta['definition_id'] != 'contract-scenario-a-' + asset:
        raise OfferError('ID Contract Definition non coerente con bootstrap; ripubblicazione bloccata.')
    if meta['access_policy'] != 'policy-catalogo-rijk' or meta['contract_policy'] != 'policy-scenario-a-' + asset:
        raise OfferError('Associazione alle policy diversa dal bootstrap approvato.')
    return {
        '@context': [MANAGEMENT_CONTEXT],
        '@type': 'ContractDefinition',
        '@id': meta['definition_id'],
        'accessPolicyId': meta['access_policy'],
        'contractPolicyId': meta['contract_policy'],
        'assetsSelector': [{
            '@type': 'Criterion',
            'operandLeft': NS + 'id',
            'operator': '=',
            'operandRight': asset,
        }],
    }


def _validate_normalized(meta, asset_id, policy_ids, asset_ids):
    if meta['asset_id'] != asset_id:
        raise OfferError('La definizione comprende un dataset diverso da quello scelto.')
    if meta['asset_id'] not in asset_ids:
        raise OfferError('Asset non registrato nel Provider; nessuna modifica applicata.')
    if meta['access_policy'] not in policy_ids or meta['contract_policy'] not in policy_ids:
        raise OfferError('Policy referenziate non registrate: operazione bloccata.')
    if meta['access_policy'] != 'policy-catalogo-rijk':
        raise OfferError('Access Policy diversa da quella approvata; operazione bloccata.')
    if not meta['contract_policy'].startswith('policy-scenario-a-'):
        raise OfferError('Contract Policy diversa dallo Scenario A: operazione bloccata.')
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', meta['definition_id']):
        raise OfferError('ID di definizione non valido.')


def _directory(root):
    folder = (Path(root) / 'ui_portale' / DIRNAME)
    # Non seguire directory simboliche, né scrivere fuori dalla copia del portale.
    if folder.is_symlink():
        raise OfferError('La directory archivio è un collegamento simbolico: operazione bloccata.')
    if folder.exists() and not folder.is_dir():
        raise OfferError('Archivio locale non valido.')
    if folder.exists() and folder.stat().st_mode & 0o077:
        raise OfferError('Permessi archivio non riservati al proprietario: correggerli prima di proseguire.')
    return folder


def _archive_path(root, asset_id):
    if not re.fullmatch(r'rijksmuseum-[a-z0-9-]{1,150}', asset_id):
        raise OfferError('Asset ID non valido.')
    return _directory(root) / (asset_id + '.json')


def _read_archive(root, asset_id):
    path = _archive_path(root, asset_id)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 300_000:
        raise OfferError('Archivio di ripubblicazione non valido.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('asset_id') != asset_id
            or not isinstance(data.get('payload'), dict)
            or data.get('sha256') != _digest(data['payload'])):
        raise OfferError('Integrità archivio non verificata: operazione bloccata.')
    return data


def _write_archive(root, asset_id, data):
    target = _archive_path(root, asset_id)
    folder = target.parent
    if not folder.exists():
        folder.mkdir(mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.offer-', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as fp:
            fp.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))
            fp.flush()
            os.fsync(fp.fileno())
        os.chmod(tmp, 0o600)
        if target.is_symlink():
            raise OfferError('Archivio non sicuro: symlink rilevato.')
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _matches(config, asset_id):
    records = _definitions(config)
    matched = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if _selector_asset(_field(record, 'assetsSelector')) == asset_id:
            matched.append(record)
    return matched


def list_offers(root, assets, labels):
    """Solo lettura: nessuna decisione simulata sullo stato delle offerte."""
    config, issue = management_config(root)
    if not config:
        return {'available': False, 'error': issue, 'items': []}
    try:
        records = _definitions(config)
        pids, aids = _policies_and_assets(config)
    except OfferError as error:
        return {'available': False, 'error': str(error), 'items': []}
    rows = []
    for asset_id in assets:
        linked = [x for x in records if _selector_asset(_field(x,'assetsSelector')) == asset_id]
        item = {'id': asset_id, 'name': labels(asset_id), 'registered': asset_id in aids,
                'status': 'unknown', 'can_revoke': False, 'can_restore': False, 'definition_id': None}
        try:
            archive = _read_archive(root, asset_id)
        except (OSError, ValueError, TypeError) as error:
            item['reason'] = 'Archivio locale non verificabile: ' + str(error)
            rows.append(item)
            continue
        if len(linked) == 1:
            try:
                meta = _normalize_definition(linked[0])
                _validate_normalized(meta, asset_id, pids, aids)
                item.update(status='published', can_revoke=True,
                            definition_id=meta['definition_id'])
            except OfferError:
                item.update(status='unknown', reason='Definizione presente ma non compatibile con la gestione sicura.')
        elif len(linked) > 1:
            item.update(status='unknown', reason='Più Contract Definition associate: modifica bloccata.')
        elif archive and archive.get('status') in ('revoked', 'prepared'):
            try:
                meta = _normalize_definition(archive['payload'])
                _validate_normalized(meta, asset_id, pids, aids)
                if _get_definition(config, meta['definition_id']) is not None:
                    raise OfferError('L’ID della definizione è ancora attivo.')
                item.update(status='revoked', can_restore=True,
                            definition_id=meta['definition_id'])
            except OfferError:
                item.update(status='unknown', reason='Archivio presente ma non ripubblicabile in sicurezza.')
        else:
            item.update(status='not_published', reason='Nessuna offerta gestita dal portale per questo asset.')
        rows.append(item)
    return {'available': True, 'items': rows}


def prepare(root, assets, session_id, asset_id, action):
    if action not in CONFIRM_WORD or asset_id not in assets or not session_id:
        raise OfferError('Operazione non consentita.')
    config, issue = management_config(root)
    if not config:
        raise OfferError(issue)
    matches = _matches(config, asset_id)
    pids, aids = _policies_and_assets(config)
    if action == 'revoke':
        if len(matches) != 1:
            raise OfferError('La revoca richiede una sola Contract Definition attiva riferita al dataset.')
        ident = simple_id(matches[0])
        record = _get_definition(config, ident)
        if not isinstance(record, dict):
            raise OfferError('Impossibile leggere la Contract Definition prima della revoca.')
        meta = _normalize_definition(record)
        _validate_normalized(meta, asset_id, pids, aids)
        digest = _digest(meta['payload'])
    else:
        if matches:
            raise OfferError('Esiste già una Contract Definition per il dataset; ripubblicazione bloccata.')
        archive = _read_archive(root, asset_id)
        if not archive or archive.get('status') not in ('revoked', 'prepared'):
            raise OfferError('Nessun archivio valido per questa offerta ritirata.')
        meta = _normalize_definition(archive['payload'])
        _validate_normalized(meta, asset_id, pids, aids)
        if _get_definition(config, meta['definition_id']) is not None:
            raise OfferError('L’ID della Contract Definition risulta già presente in EDC.')
        digest = _digest(meta['payload'])
    for key in list(TICKETS):
        if TICKETS[key]['expires'] < time.monotonic():
            del TICKETS[key]
    ticket = secrets.token_urlsafe(30)
    TICKETS[ticket] = {'expires': time.monotonic() + TICKET_TTL,
                       'session': session_id, 'asset_id': asset_id,
                       'action': action, 'digest': digest,
                       'definition_id': meta['definition_id']}
    return {'ticket': ticket, 'action': action, 'asset_id': asset_id,
            'definition_id': meta['definition_id'], 'confirm_word': CONFIRM_WORD[action],
            'expires_seconds': TICKET_TTL,
            'message': ('La revoca impedirà nuove offerte basate su questa definizione; '
                        'non elimina accordi preesistenti o JSON.' if action == 'revoke'
                        else 'Ripubblicherà la stessa definizione e le stesse policy archiviate.')}


def commit(root, assets, session_id, ticket, password_verified, confirm_word):
    challenge = TICKETS.pop(ticket, None) if isinstance(ticket, str) else None
    if not challenge or time.monotonic() > challenge['expires'] or session_id != challenge['session']:
        raise OfferError('Conferma scaduta o non associata a questa sessione. Riprovare.')
    if not password_verified or confirm_word != CONFIRM_WORD[challenge['action']]:
        raise OfferError('Chiave Provider o testo di conferma non valido; nessuna modifica eseguita.')
    asset_id, action = challenge['asset_id'], challenge['action']
    if asset_id not in assets:
        raise OfferError('Asset non presente nel registro approvato.')
    config, issue = management_config(root)
    if not config:
        raise OfferError(issue)
    matches = _matches(config, asset_id)
    pids, aids = _policies_and_assets(config)
    if action == 'revoke':
        if len(matches) != 1 or simple_id(matches[0]) != challenge['definition_id']:
            raise OfferError('Offerta modificata dalla preparazione; revoca annullata.')
        record = _get_definition(config, challenge['definition_id'])
        if not isinstance(record, dict):
            raise OfferError('Definizione EDC non più disponibile.')
        meta = _normalize_definition(record)
        _validate_normalized(meta, asset_id, pids, aids)
        if _digest(meta['payload']) != challenge['digest']:
            raise OfferError('Definizione cambiata; revoca annullata.')
        existing = _read_archive(root, asset_id)
        if existing and (existing['sha256'] != challenge['digest'] or
                         existing.get('definition_id') != meta['definition_id']):
            raise OfferError('Archivio precedente diverso; revoca annullata per evitare perdita di dati.')
        archive = {'schema': 1, 'asset_id': asset_id,
                   'definition_id': meta['definition_id'],
                   'payload': meta['payload'], 'original_get_response': record,
                   'sha256': challenge['digest'], 'status': 'prepared',
                   'archived_at': _current_utc(), 'revoked_at': None}
        _write_archive(root, asset_id, archive)  # PRIMA di qualsiasi DELETE
        _api(config, 'DELETE', '/' + quote(meta['definition_id'], safe=''))
        if _get_definition(config, meta['definition_id']) is not None:
            raise OfferError('DELETE inviata ma definizione ancora visibile; stato da verificare, archivio preservato.')
        archive['status'] = 'revoked'
        archive['revoked_at'] = _current_utc()
        _write_archive(root, asset_id, archive)
        return {'ok': True, 'action': 'revoke', 'asset_id': asset_id,
                'definition_id': meta['definition_id'], 'message': 'Revoca confermata dal Provider EDC.'}
    if matches:
        raise OfferError('Offerta già presente; ripubblicazione annullata.')
    archive = _read_archive(root, asset_id)
    if not archive or archive.get('status') not in ('revoked', 'prepared'):
        raise OfferError('Archivio di revoca non disponibile o stato non confermato.')
    meta = _normalize_definition(archive['payload'])
    _validate_normalized(meta, asset_id, pids, aids)
    if (_digest(meta['payload']) != challenge['digest'] or
            meta['definition_id'] != challenge['definition_id']):
        raise OfferError('Archivio modificato: ripubblicazione annullata.')
    if _get_definition(config, meta['definition_id']) is not None:
        raise OfferError('La Contract Definition risulta già registrata.')
    _api(config, 'POST', '', _bootstrap_compatible_creation(meta))
    new = _get_definition(config, meta['definition_id'])
    if not isinstance(new, dict) or _digest(_normalize_definition(new)['payload']) != challenge['digest']:
        raise OfferError('POST inviata, ma il risultato EDC non è confermato. Controllare prima di ripetere.')
    archive['status'] = 'republished'
    archive['republished_at'] = _current_utc()
    _write_archive(root, asset_id, archive)
    return {'ok': True, 'action': 'restore', 'asset_id': asset_id,
            'definition_id': meta['definition_id'], 'message': 'Ripubblicazione confermata dal Provider EDC.'}
