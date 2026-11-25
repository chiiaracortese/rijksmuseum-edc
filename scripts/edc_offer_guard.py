"""Protezione delle revoche intenzionali durante il bootstrap della sola copia EDC.

Non effettua chiamate EDC e non modifica alcun archivio. La V1.6 scrive una
traccia verificata della Contract Definition in ui_portale/.provider-offer-archives.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class RevocationGuardError(RuntimeError):
    pass


def should_register_contract(root: Path, asset_id: str) -> bool:
    """False solo per una revoca V1.6 autenticata nell'archivio locale.

    - Archivio assente o republished: comportamento bootstrap originale
    - Archivio revoked valido: NON ripubblicare
    - Archivio prepared/incerto, alterato o con link: STOP, mai ripubblicare
    """
    if not re.fullmatch(r'rijksmuseum-[a-z0-9-]{1,150}', asset_id):
        raise RevocationGuardError('Asset ID non valido: bootstrap bloccato')
    folder = Path(root) / 'ui_portale' / '.provider-offer-archives'
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise RevocationGuardError('Archivio revoche non valido: bootstrap bloccato')
    path = folder / (asset_id + '.json')
    if path.is_symlink():
        raise RevocationGuardError('Archivio revoche simbolico: bootstrap bloccato')
    if not path.exists():
        return True
    if not path.is_file() or path.stat().st_size > 300_000:
        raise RevocationGuardError('Archivio revoche non valido: bootstrap bloccato')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        payload = record['payload']
        computed = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':')).encode('utf-8')).hexdigest()
        selector = payload['edc:assetsSelector']
        valid = (
            record.get('schema') == 1
            and record.get('asset_id') == asset_id
            and record.get('definition_id') == 'contract-scenario-a-' + asset_id
            and record.get('sha256') == computed
            and isinstance(selector, list) and len(selector) == 1
            and selector[0].get('edc:operandRight') == asset_id
            and selector[0].get('edc:operandLeft') == 'id'
            and selector[0].get('edc:operator') == '='
            and payload.get('@id') == record['definition_id']
            and payload.get('edc:accessPolicyId') == 'policy-catalogo-rijk'
            and payload.get('edc:contractPolicyId') == 'policy-scenario-a-' + asset_id
        )
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RevocationGuardError('Archivio revoche illeggibile: bootstrap bloccato') from exc
    if not valid:
        raise RevocationGuardError('Archivio revoche non coerente: bootstrap bloccato')
    status = record.get('status')
    if status == 'republished':
        return True
    if status == 'revoked':
        return False
    raise RevocationGuardError('Revoca in stato incerto: bootstrap bloccato per proteggere le offerte')
