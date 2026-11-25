"""I test usano SOLO mock e file temporanei: nessun Docker, API EDC o rete."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from edc_client.negoziazione import prepara_richiesta, esito, esegui as negozia
from edc_client.trasferimento import prepara_richiesta as prepara_trasferimento, esegui as trasferisci
from edc_client.verifica import verifica, esegui as audit
from edc_client.evidenze import nuova

ASSET = 'rijksmuseum-sculture-10-opere-unificate'
IDENTITA = 'museum_nl_01'
DATA = b'{"objects":[{"id":"BK-NM-1229"}]}'


def asset():
    return {'asset_id': ASSET, 'filename': 'sculture.json',
            'size_bytes': len(DATA), 'sha256': hashlib.sha256(DATA).hexdigest()}


def negoziazione(autorizzata=True):
    return {'tipo': 'essenziale-negotiation', 'asset_id': ASSET,
            'consumer_id_configurato': IDENTITA, 'negotiation_id': 'neg-123',
            'final_state': 'FINALIZED' if autorizzata else 'TERMINATED',
            'agreement_id': 'agr-123' if autorizzata else None,
            'outcome': 'AUTHORIZED' if autorizzata else 'DENIED_BY_POLICY'}


def trasferimento():
    return {'tipo': 'essenziale-transfer', 'asset_id': ASSET, 'agreement_id': 'agr-123',
            'transfer_process_id': 'tp-123', 'last_state': 'STARTED'}


class EssenzialeWorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.neg = self.root / 'evidence/workflow/negoziazioni'
        self.trans = self.root / 'evidence/workflow/trasferimenti'
        self.audits = self.root / 'evidence/workflow/verifiche'
        self.progetto = self.root / 'progetto'
        self.progetto.mkdir()
        self.assets = {ASSET: asset()}

    def test_prepara_una_vera_offerta_da_catalogo(self):
        cat = {'dataset': [{'@id': ASSET, 'hasPolicy': {'@id': 'off-123',
                                                       '@type': 'Offer'}}]}
        offer_id, payload = prepara_richiesta(cat, ASSET)
        self.assertEqual(offer_id, 'off-123')
        self.assertEqual(payload['policy']['target'], ASSET)
        self.assertEqual(payload['@type'], 'ContractRequest')

    def test_non_fabbrica_offerta(self):
        with self.assertRaises(ValueError):
            prepara_richiesta({'dataset': []}, ASSET)

    def test_troppo_offerte_bloccato(self):
        cat = {'dataset': [{'@id': ASSET, 'hasPolicy': [{'@id': 'x'}, {'@id': 'y'}]}]}
        with self.assertRaises(ValueError):
            prepara_richiesta(cat, ASSET)

    def test_esiti_autorizzato_rifiutato_e_non_policy(self):
        self.assertEqual(esito('FINALIZED', 'agr-123', None), 'AUTHORIZED')
        self.assertEqual(esito('TERMINATED', None, 'Policy in scope contract.negotiation not fulfilled'), 'DENIED_BY_POLICY')
        self.assertEqual(esito('TERMINATED', None, 'Errore tecnico'), 'TERMINATED_OTHER_REASON')
        self.assertEqual(esito('FINALIZED', None, None), 'INCONSISTENT_FINALIZED')

    def test_negoziazione_negata_non_trasferibile(self):
        with self.assertRaisesRegex(ValueError, 'non autorizzata'):
            prepara_trasferimento(negoziazione(False), IDENTITA, self.assets)

    def test_negoziazione_identita_diversa_bloccata(self):
        with self.assertRaisesRegex(ValueError, 'Identità'):
            prepara_trasferimento(negoziazione(), 'university_it_01', self.assets)

    def test_negoziazione_forged_asset_bloccato(self):
        altered = negoziazione()
        altered['asset_id'] = 'non-esiste'
        with self.assertRaisesRegex(ValueError, 'Asset'):
            prepara_trasferimento(altered, IDENTITA, self.assets)

    def test_request_trasferimento_reale_usa_agreement(self):
        payload = prepara_trasferimento(negoziazione(), IDENTITA, self.assets)
        self.assertEqual(payload['@type'], 'TransferRequest')
        self.assertEqual(payload['transferType'], 'HttpData-PULL')
        self.assertEqual(payload['contractId'], 'agr-123')
        self.assertEqual(payload['assetId'], ASSET)

    def test_negozia_con_mock_e_nega(self):
        api = Mock()
        api.richiesta_catalogo.return_value = {'dataset': [{'@id': ASSET, 'hasPolicy': [{'@id': 'off-123'}]}]}
        api.invia_negoziazione.return_value = 'neg-123'
        api.leggi_negoziazione.return_value = {
            'state': 'TERMINATED', 'errorDetail': 'Policy in scope contract.negotiation not fulfilled'}
        path, record = negozia(api, ASSET, IDENTITA, self.neg, pausa=0, max_controlli=1)
        self.assertEqual(record['outcome'], 'DENIED_BY_POLICY')
        self.assertTrue(path.is_file())
        api.invia_trasferimento.assert_not_called()

    def test_negozia_con_mock_conclude_agreement(self):
        api = Mock()
        api.richiesta_catalogo.return_value = {'dataset': [{'@id': ASSET, 'hasPolicy': [{'@id': 'off-123'}]}]}
        api.invia_negoziazione.return_value = 'neg-123'
        api.leggi_negoziazione.return_value = {
            'state': 'FINALIZED', 'contractAgreementId': 'agr-123'}
        _, record = negozia(api, ASSET, IDENTITA, self.neg, pausa=0, max_controlli=1)
        self.assertEqual(record['outcome'], 'AUTHORIZED')

    def test_trasferisce_dopo_agreement_senza_ripetere(self):
        neg_path = nuova(self.neg, 'neg-test.json', negoziazione())
        api = Mock()
        api.invia_trasferimento.return_value = 'tp-123'
        api.leggi_trasferimento.return_value = {'state': 'STARTED'}
        path, value = trasferisci(api, neg_path, IDENTITA, self.assets,
                                 self.neg, self.trans, pausa=0, max_controlli=1)
        self.assertTrue(path.is_file())
        self.assertEqual(value['last_state'], 'STARTED')
        with self.assertRaisesRegex(RuntimeError, 'già un tentativo'):
            trasferisci(api, neg_path, IDENTITA, self.assets,
                        self.neg, self.trans, pausa=0, max_controlli=1)
        self.assertEqual(api.invia_trasferimento.call_count, 1)

    def test_rifiuto_non_invia_trasferimento(self):
        neg_path = nuova(self.neg, 'neg-test.json', negoziazione(False))
        api = Mock()
        with self.assertRaises(ValueError):
            trasferisci(api, neg_path, IDENTITA, self.assets,
                        self.neg, self.trans, pausa=0, max_controlli=1)
        api.invia_trasferimento.assert_not_called()

    def ricezione(self, raw=DATA, sha=None, agreement='agr-123'):
        tp = 'tp-123'
        dirname = hashlib.sha256(tp.encode()).hexdigest()
        folder = self.progetto / 'data/received/workflow' / dirname
        folder.mkdir(parents=True)
        (folder/'sculture.json').write_bytes(raw)
        (folder/'transfer-receipt.properties').write_text('\n'.join([
            f'dataflow_id={tp}', f'agreement_id={agreement}', f'asset_id={ASSET}',
            'filename=sculture.json', f'received_bytes={len(raw)}',
            f'received_sha256={sha or hashlib.sha256(raw).hexdigest()}'])+'\n')
        return folder

    def test_audit_sei_controlli_verificati(self):
        self.ricezione()
        result = verifica(trasferimento(), asset(), self.progetto)
        self.assertEqual(result['stato'], 'TRANSFER_VERIFIED')
        self.assertEqual(sum(result['checks'].values()), 6)

    def test_audit_blocca_modifica_contenuto(self):
        self.ricezione(raw=DATA + b' ')
        result = verifica(trasferimento(), asset(), self.progetto)
        self.assertEqual(result['stato'], 'FAILED_INTEGRITY')
        self.assertFalse(result['checks']['sha256_corretto'])

    def test_audit_blocca_agreement_diverso(self):
        self.ricezione(agreement='agr-ERRATO')
        result = verifica(trasferimento(), asset(), self.progetto)
        self.assertFalse(result['checks']['agreement_id_corretto'])

    def test_audit_file_assente_nessuna_finta_consegna(self):
        with self.assertRaisesRegex(RuntimeError, 'non ancora presenti'):
            verifica(trasferimento(), asset(), self.progetto)

    def test_audit_scrive_nel_progetto_studio_senza_alterare_altre_cartelle(self):
        self.ricezione()
        path_transfer = nuova(self.trans, 'transfer-test.json', trasferimento())
        result_path, result = audit(path_transfer, self.trans, self.audits, self.assets, self.progetto)
        self.assertTrue(result_path.is_file())
        self.assertEqual(result['stato'], 'TRANSFER_VERIFIED')
        self.assertFalse((self.progetto/'evidence/workflow').exists())

    def test_evidenza_fori_cartella_bloccata(self):
        src = self.root/'neg-externo.json'
        src.write_text(json.dumps(negoziazione()))
        api = Mock()
        with self.assertRaises(ValueError):
            trasferisci(api, src, IDENTITA, self.assets,
                        self.neg, self.trans, pausa=0, max_controlli=1)
        api.invia_trasferimento.assert_not_called()


if __name__ == '__main__':
    unittest.main()
