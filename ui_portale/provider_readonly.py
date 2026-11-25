"""Consultazione amministrativa sola lettura per il Provider EDC.

Nessuna modifica EDC: solo query alle Management API e lettura locale del
registro dei dataset. Le credenziali restano nel server Python (mai nel browser).
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
EDC_CONTEXT = {'@vocab': 'https://w3id.org/edc/v0.0.1/ns/'}


def properties(path):
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line[0] in '#!':
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def _port_reachable(port):
    """Prova TCP solo su loopback; non considera il ping prova della API EDC."""
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.8):
            return True
    except OSError:
        return False


def _docker_published_port(private_port, role="provider"):
    """Legge una mappatura Docker esistente, senza creare o modificare container."""
    if role not in ("provider", "consumer"):
        return []
    try:
        result = subprocess.run(
            ['docker', 'port', f'rijksmuseum-edc-interfaccia-{role}-1', f'{private_port}/tcp'],
            capture_output=True, text=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    ports = []
    for line in result.stdout.splitlines():
        # docker port può restituire 0.0.0.0:XXXXX, 127.0.0.1:XXXXX o [::]:XXXXX.
        match = re.search(r':(\d{1,5})$', line.strip())
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535 and port not in ports:
                ports.append(port)
    return ports


def management_config(root=ROOT, role="provider"):
    if role not in ("provider", "consumer"):
        return None, "Ruolo Management non ammesso."
    p = properties(root / f'edc/{role}/config.properties')
    # Il file configura la porta INTERNA al container, non necessariamente la porta del Mac.
    port_str = p.get('web.http.management.port', '')
    if not port_str.isdecimal() or not 1 <= int(port_str) <= 65535:
        return None, f'Porta Management API {role} non ricavabile da edc/{role}/config.properties.'
    container_port = int(port_str)
    prefix = p.get('web.http.management.path', '/management').rstrip('/')
    if not prefix.startswith('/') or '//' in prefix or '..' in prefix:
        return None, 'Percorso Management API non valido nella configurazione.'
    # Questa è la proprietà effettivamente rilevata nella copia installata dell'utente.
    key = (p.get('web.http.management.auth.key') or
           p.get('edc.api.auth.key') or
           p.get('edc.api.management.auth.key'))
    if not key or key.startswith('${'):
        return None, f'Chiave Management API {role} non disponibile localmente; query non effettuata.'
    mapped = _docker_published_port(container_port, role)
    candidates = mapped + ([container_port] if container_port not in mapped else [])
    host_port = next((x for x in candidates if _port_reachable(x)), None)
    if host_port is None:
        published = ', '.join(map(str, mapped)) if mapped else 'nessuna mappatura individuata'
        return None, (
            f'Management API non raggiungibile dal Mac su 127.0.0.1. '
            f'Porta interna {container_port}; porte host Docker: {published}. '
            f'Controllare `docker port rijksmuseum-edc-interfaccia-{role}-1 '
            f'{container_port}/tcp` e la pubblicazione della porta, senza modificare EDC.')
    return {'base': f'http://127.0.0.1:{host_port}{prefix}', 'key': key,
            'participant': p.get('edc.participant.id')}, None


def fetch_query(config, resource):
    path = '/v4/' + resource + '/request'
    body = json.dumps({'@context': EDC_CONTEXT, '@type': 'QuerySpec', 'offset': 0, 'limit': 1000}).encode()
    request = Request(config['base'] + path, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/json',
        'X-Api-Key': config['key']})
    try:
        with urlopen(request, timeout=4) as res:
            reply = json.load(res)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        kind = 'HTTP ' + str(exc.code) if isinstance(exc, HTTPError) else 'Servizio non raggiungibile o risposta non leggibile'
        return None, kind + f' ({resource}).'
    if not isinstance(reply, list):
        return None, f'Risposta {resource} non compatibile con un elenco.'
    if len(reply) >= 1000:
        return reply, f'Risultato {resource} limitato a 1000 record; elenco potenzialmente incompleto.'
    return reply, None



def fetch_full_history(config, resource):
    """Query EDC paginata, senza filtro sugli stati e senza affidarsi all'ordine dell'API.

    Non scrive nulla sul connettore: tutte le richieste sono QuerySpec di lettura.
    Ogni pagina viene controllata per evitare risultati duplicati o API che ignorano
    offset. Se la storia è incompleta, la UI non potrà chiamare 'ultimi' i record.
    """
    page_size, maximum = 200, 5000
    rows, seen = [], set()
    for offset in range(0, maximum, page_size):
        body = json.dumps({'@context': EDC_CONTEXT, '@type': 'QuerySpec',
                           'offset': offset, 'limit': page_size}).encode()
        request = Request(config['base'] + '/v4/' + resource + '/request',
                          data=body, method='POST', headers={
            'Content-Type': 'application/json', 'Accept': 'application/json',
            'X-Api-Key': config['key']})
        try:
            with urlopen(request, timeout=5) as response:
                batch = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            kind = 'HTTP ' + str(exc.code) if isinstance(exc, HTTPError) else 'Risposta non disponibile'
            return (rows if rows else None), f'Cronologia {resource} incompleta: {kind}.'
        if not isinstance(batch, list):
            return (rows if rows else None), f'Cronologia {resource}: risposta non valida.'
        for item in batch:
            if not isinstance(item, dict):
                continue
            item_id = simple_id(item)
            # La paginazione può ripetere record se il database cambia durante la lettura.
            if item_id is not None:
                if str(item_id) in seen:
                    return rows, f'Cronologia {resource} potenzialmente incompleta (paginazione instabile).'
                seen.add(str(item_id))
            rows.append(item)
        if len(batch) < page_size:
            return rows, None
    return rows, f'Cronologia {resource} limitata a {maximum} record: ordine globale non garantito.'


def _enrich_missing_dates(config, resource, rows):
    """Recupera timestamp e motivi TERMINATED assenti nella risposta sintetica.

    Il GET è una operazione di sola lettura e non cambia lo stato di negoziazione.
    """
    from urllib.parse import quote
    needs = [r for r in rows if isinstance(r, dict) and (
        not any(prop(r, k) is not None for k in ('createdAt', 'stateTimestamp', 'updatedAt'))
        or (str(prop(r, 'state') or '').upper() == 'TERMINATED'
            and not (prop(r, 'errorDetail') or prop(r, 'errorMessage'))))]
    if len(needs) > 80:
        return rows
    for item in needs:
        rid = simple_id(item)
        if not rid or len(str(rid)) > 200:
            continue
        address = config['base'] + '/v4/' + resource + '/' + quote(str(rid), safe='')
        request = Request(address, method='GET', headers={
            'Accept': 'application/json', 'X-Api-Key': config['key']})
        try:
            with urlopen(request, timeout=2) as response:
                detail = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
        if not isinstance(detail, dict) or str(simple_id(detail)) != str(rid):
            continue
        for key in ('createdAt', 'stateTimestamp', 'updatedAt', 'errorDetail', 'errorMessage',
                    'assetId', 'contractAgreementId'):
            if prop(item, key) is None and prop(detail, key) is not None:
                item[key] = prop(detail, key)
    return rows


def _local_evidence_assets(root, asset_ids):
    """Recupera soltanto associazioni ID -> dataset da evidenze locali verificabili."""
    evidence = root / 'evidence/workflow/negoziazioni'
    if not evidence.is_dir() or evidence.is_symlink():
        return {}
    pairs = {}
    for path in list(evidence.glob('*.json'))[:3000]:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 400_000:
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        rid = record.get('negotiation_id') or record.get('contract_negotiation_id')
        asset = record.get('asset_id')
        if isinstance(rid, str) and rid and asset in asset_ids:
            pairs[rid] = asset
    return pairs

def simple_id(record):
    if not isinstance(record, dict):
        return None
    return record.get('@id') or record.get('id')


def prop(record, name):
    if not isinstance(record, dict):
        return None
    return record.get(name, record.get('https://w3id.org/edc/v0.0.1/ns/' + name))


def _negotiation_failure_kind(value):
    """Classifica soltanto motivi espliciti restituiti da EDC.

    Non spedisce il messaggio diagnostico integrale al browser: può includere
    dettagli interni o informazioni sulle attestazioni del Consumer.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    detail = value.casefold()
    if (('policy' in detail and any(x in detail for x in
            ('not fulfilled', 'not satisfied', 'not permitted', 'denied', 'failed',
             'non soddisfatt', 'non rispettat', 'non valida'))) or
        'scope contract.negotiation not fulfilled' in detail):
        return 'policy'
    if (any(x in detail for x in ('credential', 'attestation', 'credenzial', 'attestazion')) and
        any(x in detail for x in ('invalid', 'missing', 'expired', 'not valid',
                                  'not found', 'denied', 'not accepted',
                                  'scadut', 'mancant', 'non valid'))):
        return 'credentials'
    if any(x in detail for x in ('unauthorized', 'not authorized', 'forbidden',
                                  'access denied', 'permission denied',
                                  'accesso negato', 'non autorizzat')):
        return 'authorization'
    return None


def _brief(rows, kind, origin="Provider", evidence_assets=None):
    result = []
    for r in rows[:1000]:
        if not isinstance(r, dict):
            continue
        entry = {'id': str(simple_id(r) or 'Non disponibile')}
        if kind == 'contracts':
            entry['access_policy'] = prop(r, 'accessPolicyId')
            entry['contract_policy'] = prop(r, 'contractPolicyId')
            entry['asset_selector'] = prop(r, 'assetsSelector')
        elif kind == 'negotiations':
            entry['state'] = prop(r, 'state')
            entry['agreement_id'] = prop(r, 'contractAgreementId')
            entry['asset_id'] = prop(r, 'assetId') or (evidence_assets or {}).get(entry['id'])
            entry['origin'] = origin
            # TERMINATED non basta a dimostrare un rifiuto per credenziali.
            # Il motivo viene classificato solo se è presente nelle API EDC.
            detail = prop(r, 'errorDetail') or prop(r, 'errorMessage')
            entry['failure_kind'] = (_negotiation_failure_kind(detail)
                                     if str(entry['state']).upper() == 'TERMINATED' else None)
        elif kind == 'transfers':
            entry['state'] = prop(r, 'state')
            entry['agreement_id'] = prop(r, 'contractId') or prop(r, 'contractAgreementId')
            entry['asset_id'] = prop(r, 'assetId')
            entry['origin'] = origin
        if kind in ('negotiations', 'transfers'):
            # Preserviamo i timestamp restituiti da EDC, senza assegnare date inventate.
            # Le API possono esporli sia come termini semplici sia con prefisso JSON-LD.
            entry['created_at'] = prop(r, 'createdAt') or r.get('edc:createdAt')
            entry['state_timestamp'] = prop(r, 'stateTimestamp') or r.get('edc:stateTimestamp')
            entry['updated_at'] = prop(r, 'updatedAt') or r.get('edc:updatedAt')
        result.append(entry)
    return result


def snapshot(root, assets, label_function):
    config, issue = management_config(root)
    data = {'provider_id': properties(root / 'edc/provider/config.properties').get('edc.participant.id'),
            'configured_count': len(assets), 'asset_api': None,
            'registered_count': None, 'policy_count': None, 'contract_count': None,
            'offers_count': None,  # non deducibile dal solo numero di Contract Definition
            'dataplane_state': None, 'controlplane_state': 'NON VERIFICATO',
            'policies': [], 'contracts': [], 'negotiations': [], 'consumer_negotiations': [], 'transfers': [],
            'messages': [], 'assets': [], 'available': {'negotiations': False, 'transfers': False},
            'potentially_incomplete_history': False, 'consumer_history_available': False}
    for asset_id, a in assets.items():
        entry = {'id': asset_id, 'name': label_function(asset_id),
                 'registered': None, 'works': None, 'source': 'NON VERIFICATA'}
        try:
            objects = load_local_objects(root, asset_id, a)
            entry['works'] = len(objects)
            entry['source'] = 'JSON LOCALE DISPONIBILE'
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        data['assets'].append(entry)
    if not config:
        data['messages'].append(issue)
        data['messages'].append('Stato Control Plane e Data Plane non verificato. Nessun dato fittizio visualizzato.')
        return data
    resource_map = {'assets': 'assets', 'policydefinitions': 'policies',
                    'contractdefinitions': 'contracts', 'contractnegotiations': 'negotiations',
                    'transferprocesses': 'transfers'}
    replies = {}
    for resource, field in resource_map.items():
        if field in ('negotiations', 'transfers'):
            rows, error = fetch_full_history(config, resource)
            if rows is not None:
                rows = _enrich_missing_dates(config, resource, rows)
        else:
            rows, error = fetch_query(config, resource)
        if error:
            data['messages'].append(error)
            if field in ('negotiations', 'transfers'):
                data['potentially_incomplete_history'] = True
        if rows is not None:
            replies[field] = rows
    if 'assets' in replies:
        ids = {str(simple_id(row)) for row in replies['assets'] if simple_id(row)}
        data['registered_count'] = len(ids)
        for entry in data['assets']:
            entry['registered'] = entry['id'] in ids
        data['asset_api'] = 'Management API Provider'
        data['controlplane_state'] = 'API MANAGEMENT RAGGIUNGIBILE'
    else:
        data['messages'].append('Il Control Plane non è stato verificato attraverso l’API Asset.')
    if 'policies' in replies:
        data['policy_count'] = len(replies['policies'])
        data['policies'] = [{'id': str(simple_id(r) or 'Non disponibile')} for r in replies['policies'] if isinstance(r, dict)]
    if 'contracts' in replies:
        data['contract_count'] = len(replies['contracts'])
        data['contracts'] = _brief(replies['contracts'], 'contracts')
    if 'negotiations' in replies:
        data['available']['negotiations'] = True
        data['negotiations'] = _brief(replies['negotiations'], 'negotiations', 'Provider',
                                       _local_evidence_assets(root, set(assets.keys())))
    if 'transfers' in replies:
        data['available']['transfers'] = True
        data['transfers'] = _brief(replies['transfers'], 'transfers')
    # Per vedere richieste rifiutate prima dell'arrivo al Provider, leggiamo anche
    # la cronologia del Consumer; nessuna scrittura e nessuna modifica al workflow.
    # La provenienza è esplicita: un record solo sul Consumer NON viene descritto
    # come una negoziazione registrata dal Provider.
    consumer_config, consumer_issue = management_config(root, 'consumer')
    if consumer_config:
        consumer_rows, consumer_error = fetch_full_history(consumer_config, 'contractnegotiations')
        if consumer_error:
            data['potentially_incomplete_history'] = True
            data['messages'].append('Cronologia Consumer parziale: ' + consumer_error)
        if consumer_rows is not None:
            consumer_rows = _enrich_missing_dates(consumer_config, 'contractnegotiations', consumer_rows)
            # Il portale gestisce un solo Provider: non uniamo trattative con altri connettori.
            provider_id = config.get('participant')
            consumer_rows = [r for r in consumer_rows if not prop(r, 'counterPartyId') or
                             prop(r, 'counterPartyId') == provider_id]
            evidence_assets = _local_evidence_assets(root, set(assets.keys()))
            data['consumer_negotiations'] = _brief(consumer_rows, 'negotiations',
                                                   'Consumer', evidence_assets)
            data['consumer_history_available'] = True
            data['available']['negotiations'] = True
    else:
        # Non si dichiara completa una cronologia che può omettere richieste
        # respinte e presenti soltanto sul Consumer.
        data['potentially_incomplete_history'] = True
        data['messages'].append('Cronologia Consumer non consultabile: ' + consumer_issue)

    data['messages'].append('Stato del Data Plane: non verificabile con le query Management API disponibili.')
    data['messages'].append('Offerte pubblicate: non quantificate senza la verifica effettiva del catalogo DSP.')
    return data


def _safe_path(root, candidate):
    root = root.resolve()
    if not isinstance(candidate, str) or not candidate.strip():
        raise ValueError('Percorso dataset assente')
    # Sono consentiti solo percorsi relativi alla copia; escludere cartelle sensibili.
    if candidate.startswith('/project/data/'):
        candidate = candidate.removeprefix('/project/')
    path = Path(candidate)
    if path.is_absolute() or '..' in path.parts or path.suffix.lower() != '.json':
        raise ValueError('Percorso dataset non ammesso')
    resolved = (root / path).resolve()
    if root not in resolved.parents or not resolved.is_file() or resolved.is_symlink():
        raise ValueError('JSON sorgente assente nella copia del progetto')
    # Il Provider non legge MAI data/received: quel percorso è riservato al Consumer.
    originals = (root / 'data/rijksmuseum').resolve()
    if originals not in resolved.parents:
        raise ValueError('Il JSON non proviene da data/rijksmuseum (sorgenti Provider)')
    if resolved.stat().st_size > 30_000_000:
        raise ValueError('Dimensione JSON non ammessa')
    return resolved


def _candidate_paths(root, asset_id, asset):
    keys = ('source_path', 'source_file', 'file_path', 'json_path', 'dataset_path', 'path')
    for key in keys:
        value = asset.get(key)
        if isinstance(value, str):
            yield value
    # Mappatura esplicita già presente nel registro delle sorgenti (se disponibile).
    property_file = root / 'config/edc-assets.properties'
    if property_file.is_file() and not property_file.is_symlink():
        for key, value in properties(property_file).items():
            if asset_id in key and value.endswith('.json'):
                yield value
    # Un mapping amministrativo locale NON modifica il registro asset.
    mapping_file = root / 'ui_portale/provider_sources.json'
    if mapping_file.is_file() and not mapping_file.is_symlink():
        mapping = json.loads(mapping_file.read_text(encoding='utf-8'))
        if isinstance(mapping, dict) and isinstance(mapping.get(asset_id), str):
            yield mapping[asset_id]
    # Associazione verificabile sul modello di nomi dei 14 file originali.
    # Questi sono file Provider, MAI le copie ricevute in data/received/workflow.
    match = re.fullmatch(r'rijksmuseum-([a-z0-9-]+)-10-opere-unificate', asset_id)
    if match:
        slug = match.group(1).replace('-', '_')
        yield f'data/rijksmuseum/rijksmuseum_{slug}_10_opere_unificate.json'
    # Fallback prudente: un solo file JSON omonimo all'asset sotto data/.
    data_dir = root / 'data'
    if data_dir.is_dir():
        for candidate in (f'{asset_id}.json', f'{asset_id.removeprefix("rijksmuseum-")}.json'):
            found = list(data_dir.rglob(candidate))
            if len(found) == 1:
                yield str(found[0].relative_to(root))


def load_local_objects(root, asset_id, asset):
    if asset_id != asset.get('asset_id'):
        raise ValueError('Asset non corrispondente al registro')
    issues = []
    for candidate in _candidate_paths(root, asset_id, asset):
        try:
            path = _safe_path(root, candidate)
            objects = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(objects, list) or not all(isinstance(v, dict) for v in objects):
                raise ValueError('Il JSON sorgente non è una lista di opere')
            return objects
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            issues.append(str(exc))
    raise ValueError('JSON locale non individuato in modo verificabile per questo asset. '
                     'Controllare il registro o configurare ui_portale/provider_sources.json; '
                     + (issues[0] if issues else 'nessuna mappatura file esplicita'))
