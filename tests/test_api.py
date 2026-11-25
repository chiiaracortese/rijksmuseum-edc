import json
import unittest
from unittest.mock import patch
from edc_client.edc_api import ClientEDC


class Response:
    status = 200
    def __init__(self, data):
        self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self): return json.dumps(self.data).encode()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.api = ClientEDC('http://127.0.0.1:41293/management/v4', 'segreto')

    def test_negoziazione_post_context(self):
        with patch('edc_client.edc_api.apri', return_value=Response({'@id': 'neg-01'})) as called:
            self.assertEqual(self.api.invia_negoziazione({'@type': 'ContractRequest'}), 'neg-01')
            req = called.call_args.args[0]
            self.assertEqual(req.get_method(), 'POST')
            self.assertTrue(req.full_url.endswith('/contractnegotiations'))
            self.assertEqual(json.loads(req.data)['@type'], 'ContractRequest')
            self.assertEqual(req.headers['X-api-key'], 'segreto')

    def test_trasferimento_post_context(self):
        with patch('edc_client.edc_api.apri', return_value=Response({'@id': 'tp-01'})) as called:
            self.assertEqual(self.api.invia_trasferimento({'@type': 'TransferRequest'}), 'tp-01')
            req = called.call_args.args[0]
            self.assertTrue(req.full_url.endswith('/transferprocesses'))
            self.assertEqual(json.loads(req.data)['@type'], 'TransferRequest')

    def test_stati_get(self):
        with patch('edc_client.edc_api.apri', return_value=Response({'state': 'FINALIZED'})) as called:
            self.assertEqual(self.api.leggi_negoziazione('neg-01')['state'], 'FINALIZED')
            self.assertEqual(called.call_args.args[0].get_method(), 'GET')

    def test_endpoint_esterno_non_permesso(self):
        with self.assertRaises(ValueError):
            ClientEDC('http://example.com/management/v4', 'segreto')

    def test_identificativo_path_non_sicuro_bloccato(self):
        with patch('edc_client.edc_api.apri') as called:
            with self.assertRaises(ValueError):
                self.api.leggi_negoziazione('../other')
            called.assert_not_called()


if __name__ == '__main__': unittest.main()
