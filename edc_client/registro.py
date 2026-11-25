"""Registro degli asset (quali dataset sono registrati NEL progetto, non nel catalogo EDC)."""
import json
import re
from pathlib import Path

_ASSET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def leggi_asset(progetto: Path) -> dict[str, dict]:
    """Legge e valida il manifest locale; non legge o pubblica i JSON delle opere."""
    path = progetto / 'config/edc-assets.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Versione del registro asset non supportata')
    assets = data.get('assets')
    if not isinstance(assets, list) or not assets:
        raise ValueError('Nessun asset valido nel registro')
    output = {}
    filenames = set()
    for record in assets:
        if not isinstance(record, dict):
            raise ValueError('Record asset non valido')
        asset_id, filename = record.get('asset_id'), record.get('filename')
        if (not isinstance(asset_id, str) or not _ASSET_ID.fullmatch(asset_id) or
                not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.json', filename)):
            raise ValueError('Identificativo o nome file non valido')
        if asset_id in output or filename in filenames:
            raise ValueError('Asset o nome file duplicato')
        if not isinstance(record.get('size_bytes'), int) or record['size_bytes'] <= 0:
            raise ValueError('Dimensione asset non valida')
        if not isinstance(record.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', record['sha256']):
            raise ValueError('Impronta SHA-256 asset non valida')
        filenames.add(filename)
        output[asset_id] = record
    return output
