"""Un accordo EDC valido può dar luogo ad un solo tentativo di TransferRequest."""
import hashlib
import time
from pathlib import Path
from .evidenze import ora, nuova, salva, leggi, controlla_id


def prepara_richiesta(negoziazione: dict, identita: str, asset_attesi: dict) -> dict:
    if negoziazione.get('tipo') != 'essenziale-negotiation':
        raise ValueError('Non è un’evidenza di negoziazione Essenziale')
    asset = negoziazione.get('asset_id')
    if asset not in asset_attesi:
        raise ValueError('Asset non previsto nel registro locale')
    if negoziazione.get('consumer_id_configurato') != identita:
        raise ValueError('Identità configurata diversa da quella della negoziazione')
    if (negoziazione.get('final_state') != 'FINALIZED'
            or negoziazione.get('outcome') != 'AUTHORIZED'):
        raise ValueError('Negoziazione non autorizzata: trasferimento bloccato')
    accordo = controlla_id(negoziazione.get('agreement_id'), 'Agreement ID')
    controlla_id(negoziazione.get('negotiation_id'), 'Negotiation ID')
    return {'@context': {'@vocab': 'https://w3id.org/edc/v0.0.1/ns/'},
            '@type': 'TransferRequest', 'assetId': asset, 'contractId': accordo,
            'counterPartyId': 'provider',
            'counterPartyAddress': 'http://provider:19194/protocol/2025-1',
            'protocol': 'dataspace-protocol-http:2025-1',
            'transferType': 'HttpData-PULL'}


def esegui(api, path_negoziazione: Path, identita: str, asset_attesi: dict,
           dir_negoziazioni: Path, dir_trasferimenti: Path, pausa=1.0, max_controlli=60):
    negoziazione = leggi(path_negoziazione, dir_negoziazioni)
    payload = prepara_richiesta(negoziazione, identita, asset_attesi)
    negoziazione_id = negoziazione['negotiation_id']
    # Il nome deterministico riserva il diritto a un unico tentativo per accordo.
    nome = 'transfer-' + hashlib.sha256(negoziazione_id.encode()).hexdigest() + '.json'
    evidenza = {
        'tipo': 'essenziale-transfer', 'creato_utc': ora(),
        'asset_id': payload['assetId'], 'consumer_id_configurato': identita,
        'negotiation_id': negoziazione_id, 'agreement_id': payload['contractId'],
        'submission_status': 'RESERVED_NOT_SUBMITTED',
        'transfer_process_id': None, 'stati_osservati': [], 'last_state': None}
    try:
        path = nuova(dir_trasferimenti, nome, evidenza)
    except FileExistsError:
        raise RuntimeError('Esiste già un tentativo di trasferimento per questa negoziazione') from None
    try:
        evidenza['submission_status'] = 'SUBMISSION_UNCERTAIN'
        salva(path, evidenza)
        transfer_id = controlla_id(api.invia_trasferimento(payload), 'Transfer Process ID')
        evidenza['transfer_process_id'] = transfer_id
        evidenza['submission_status'] = 'POST_ACCEPTED'
        salva(path, evidenza)
        for i in range(max_controlli):
            risposta = api.leggi_trasferimento(transfer_id)
            stato = risposta.get('state')
            if not isinstance(stato, str):
                raise RuntimeError('Stato Transfer Process EDC non disponibile')
            if not evidenza['stati_osservati'] or evidenza['stati_osservati'][-1] != stato:
                evidenza['stati_osservati'].append(stato)
            evidenza['last_state'] = stato
            salva(path, evidenza)
            if stato in ('STARTED', 'COMPLETED', 'TERMINATED', 'SUSPENDED'):
                break
            if i < max_controlli - 1:
                time.sleep(pausa)
        if evidenza['last_state'] in ('TERMINATED', 'SUSPENDED'):
            raise RuntimeError('Trasferimento terminato o sospeso')
        if evidenza['last_state'] not in ('STARTED', 'COMPLETED'):
            raise RuntimeError('Stato del trasferimento non conclusivo')
    except Exception as exc:
        evidenza['errore_operativo'] = str(exc)
        salva(path, evidenza)
        raise RuntimeError(f'{exc} | evidenza: {path}') from None
    return path, evidenza
