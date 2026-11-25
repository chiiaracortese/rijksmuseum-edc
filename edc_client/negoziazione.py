"""Solo discovery dell'offerta -> POST ContractRequest -> lettura stati EDC."""
import secrets
import time
from pathlib import Path
from .discovery import estrai_offerte
from .evidenze import ora, nuova, salva, controlla_id

PROVIDER = 'http://provider:19194/protocol/2025-1'


def prepara_richiesta(catalogo: dict, asset_id: str) -> tuple[str, dict]:
    """Non riusa offerte di un altro asset e non fabbrica la policy."""
    offerte = estrai_offerte(catalogo)
    if asset_id not in offerte or len(offerte[asset_id]) != 1:
        raise ValueError('Serve una sola offerta EDC per l’asset richiesto')
    datasets = catalogo['dataset']
    if isinstance(datasets, dict):
        datasets = [datasets]
    dataset = next(d for d in datasets if d['@id'] == asset_id)
    originale = dataset['hasPolicy']
    if isinstance(originale, dict):
        originale = [originale]
    offer = dict(originale[0])
    offer_id = offer.get('@id')
    if not isinstance(offer_id, str) or not offer_id or len(offer_id) > 1024:
        raise ValueError('Offer ID assente o non valido')
    offer['assigner'] = 'provider'
    offer['target'] = asset_id
    return offer_id, {
        '@context': [
            'https://w3id.org/dspace/2025/1/odrl-profile.jsonld',
            {'@vocab': 'https://w3id.org/edc/v0.0.1/ns/',
             'edc': 'https://w3id.org/edc/v0.0.1/ns/',
             'odrl': 'http://www.w3.org/ns/odrl/2/'}],
        '@type': 'ContractRequest',
        'counterPartyId': 'provider',
        'counterPartyAddress': PROVIDER,
        'protocol': 'dataspace-protocol-http:2025-1',
        'policy': offer}


def esito(stato: str, accordo: str | None, dettaglio: str | None) -> str:
    if stato == 'FINALIZED':
        return 'AUTHORIZED' if accordo else 'INCONSISTENT_FINALIZED'
    if stato == 'TERMINATED':
        if accordo:
            return 'INCONSISTENT_TERMINATED'
        if 'policy in scope contract.negotiation not fulfilled' in str(dettaglio or '').lower():
            return 'DENIED_BY_POLICY'
        return 'TERMINATED_OTHER_REASON'
    return 'NOT_CONCLUSIVE'


def esegui(api, asset_id: str, identita: str, dir_evidenze: Path, pausa=1.0, max_controlli=60):
    # La prima API è sempre il catalogo: EDC, non il manifest locale, fornisce l'offerta.
    offer_id, payload = prepara_richiesta(api.richiesta_catalogo(), asset_id)
    evidenza = {
        'tipo': 'essenziale-negotiation', 'creato_utc': ora(), 'asset_id': asset_id,
        'consumer_id_configurato': identita, 'offer_id': offer_id,
        'submission_status': 'RESERVED_NOT_SUBMITTED', 'negotiation_id': None,
        'final_state': None, 'agreement_id': None, 'outcome': None,
        'stati_osservati': []}
    nome = 'neg-' + secrets.token_hex(12) + '.json'
    path = nuova(dir_evidenze, nome, evidenza)
    try:
        # Un timeout del POST è ambiguo: non ripetere automaticamente.
        evidenza['submission_status'] = 'SUBMISSION_UNCERTAIN'
        salva(path, evidenza)
        negoziazione_id = controlla_id(api.invia_negoziazione(payload), 'Negotiation ID')
        evidenza['negotiation_id'] = negoziazione_id
        evidenza['submission_status'] = 'POST_ACCEPTED'
        salva(path, evidenza)
        for i in range(max_controlli):
            stato = api.leggi_negoziazione(negoziazione_id)
            nome_stato = stato.get('state')
            if not isinstance(nome_stato, str):
                raise RuntimeError('Stato EDC non disponibile')
            if not evidenza['stati_osservati'] or evidenza['stati_osservati'][-1] != nome_stato:
                evidenza['stati_osservati'].append(nome_stato)
            evidenza['final_state'] = nome_stato
            evidenza['agreement_id'] = stato.get('contractAgreementId')
            evidenza['error_detail'] = stato.get('errorDetail')
            evidenza['outcome'] = esito(nome_stato, evidenza['agreement_id'], evidenza['error_detail'])
            salva(path, evidenza)
            if nome_stato in ('FINALIZED', 'TERMINATED'):
                break
            if i < max_controlli - 1:
                time.sleep(pausa)
        if evidenza['outcome'] == 'NOT_CONCLUSIVE':
            raise RuntimeError('Negoziazione non conclusa; consultare l’evidenza')
    except Exception as exc:
        evidenza['errore_operativo'] = str(exc)
        salva(path, evidenza)
        raise RuntimeError(f'{exc} | evidenza: {path}') from None
    return path, evidenza
