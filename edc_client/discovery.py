"""Converte la risposta del catalogo EDC in una vista didattica semplice."""


def estrai_offerte(catalogo: dict) -> dict[str, list[str]]:
    """Restituisce asset ID -> elenco degli offer ID rilevati dalla risposta EDC."""
    datasets = catalogo.get('dataset', [])
    if isinstance(datasets, dict):
        datasets = [datasets]
    if not isinstance(datasets, list):
        raise ValueError('Campo dataset del catalogo inatteso')
    offerte = {}
    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise ValueError('Elemento del catalogo non valido')
        asset_id = dataset.get('@id')
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError('Asset senza identificativo nel catalogo')
        if asset_id in offerte:
            raise ValueError('Asset ripetuto nel catalogo')
        policies = dataset.get('hasPolicy', [])
        if isinstance(policies, dict):
            policies = [policies]
        if not isinstance(policies, list):
            raise ValueError('Elenco delle offerte inatteso')
        offer_ids = []
        for policy in policies:
            if not isinstance(policy, dict) or not isinstance(policy.get('@id'), str):
                raise ValueError(f'Offerta non leggibile per {asset_id}')
            offer_ids.append(policy['@id'])
        offerte[asset_id] = offer_ids
    return offerte


def confronta(registro: dict, offerte: dict) -> list[dict]:
    """Confronta gli asset ATTESI (manifest) con quelli EFFETTIVAMENTE annunciati da EDC."""
    return [{
        'asset_id': ident,
        'filename': item['filename'],
        'pubblicato_in_edc': ident in offerte,
        'numero_offerte': len(offerte.get(ident, [])),
        'offer_ids': offerte.get(ident, []),
    } for ident, item in sorted(registro.items())]
