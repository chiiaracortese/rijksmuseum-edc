"""Controlla il JSON materialmente ricevuto: 6 riscontri identici al workflow validato."""
import hashlib
import json
from pathlib import Path
from .evidenze import leggi, nuova, controlla_id, ora


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for blocco in iter(lambda: source.read(1048576), b''):
            digest.update(blocco)
    return digest.hexdigest()


def leggi_properties(path: Path) -> dict:
    """Le ricevute Java sono prodotte con java.util.Properties.store()."""
    result = {}
    for line in path.read_text(encoding='iso-8859-1').splitlines():
        if not line or line.startswith(('#', '!')):
            continue
        if '=' not in line:
            raise ValueError('Riga della ricevuta non valida')
        key, _, value = line.partition('=')
        if key.strip() in result:
            raise ValueError('Proprietà della ricevuta duplicata')
        result[key.strip()] = value.strip()
    return result


def verifica(transfer: dict, asset: dict, progetto: Path) -> dict:
    """Nessun download: legge solo la ricevuta e il file già scritti dal Data Plane."""
    if transfer.get('tipo') != 'essenziale-transfer' or transfer.get('last_state') not in ('STARTED', 'COMPLETED'):
        raise ValueError('Trasferimento non idoneo alla verifica')
    transfer_id = controlla_id(transfer.get('transfer_process_id'), 'Transfer Process ID')
    if transfer.get('asset_id') != asset['asset_id']:
        raise ValueError('Asset del trasferimento diverso dal registro')
    folder = progetto / 'data/received/workflow' / hashlib.sha256(transfer_id.encode()).hexdigest()
    ricevuta = folder / 'transfer-receipt.properties'
    file = folder / asset['filename']
    if any(p.is_symlink() for p in (folder, ricevuta, file)):
        raise ValueError('Collegamento simbolico nella cartella di ricezione')
    if not ricevuta.is_file() or not file.is_file():
        raise RuntimeError('File e ricevuta non ancora presenti; ripetere SOLO il comando verifica')
    props = leggi_properties(ricevuta)
    actual_hash = sha256_file(file)
    checks = {
        'dataflow_id_corretto': props.get('dataflow_id') == transfer_id,
        'agreement_id_corretto': props.get('agreement_id') == transfer.get('agreement_id'),
        'asset_id_corretto': props.get('asset_id') == asset['asset_id'],
        'filename_corretto': props.get('filename') == asset['filename'],
        'dimensione_byte_corretta': file.stat().st_size == asset['size_bytes'] == int(props.get('received_bytes', '-1')),
        'sha256_corretto': actual_hash == asset['sha256'] == props.get('received_sha256'),
    }
    return {'stato': 'TRANSFER_VERIFIED' if all(checks.values()) else 'FAILED_INTEGRITY',
            'checks': checks, 'sha256_ricevuto': actual_hash,
            'file_relativo': str(file.relative_to(progetto)),
            'ricevuta_relativa': str(ricevuta.relative_to(progetto))}


def esegui(path_transfer: Path, dir_trasferimenti: Path, dir_verifiche: Path,
           assets: dict, progetto: Path):
    transfer = leggi(path_transfer, dir_trasferimenti)
    asset = assets.get(transfer.get('asset_id'))
    if not asset:
        raise ValueError('Asset non presente nel registro')
    result = verifica(transfer, asset, progetto)
    result.update({'tipo': 'essenziale-audit', 'creato_utc': ora(),
                   'asset_id': asset['asset_id'],
                   'transfer_process_id': transfer['transfer_process_id'],
                   'agreement_id': transfer['agreement_id']})
    nome = 'audit-' + hashlib.sha256(transfer['transfer_process_id'].encode()).hexdigest() + '.json'
    path = nuova(dir_verifiche, nome, result)
    return path, result
