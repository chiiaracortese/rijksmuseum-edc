import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
from edc_client.registro import leggi_asset
from edc_client.discovery import estrai_offerte, confronta
from edc_client.edc_api import ClientEDC, leggi_chiave_consumer


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root/'config').mkdir()
        (self.root/'edc/consumer').mkdir(parents=True)
        (self.root/'config/edc-assets.json').write_text(json.dumps({'schema_version': 1, 'assets': [
            {'asset_id': 'rijksmuseum-sculture-10-opere-unificate', 'filename': 'sculture.json',
             'size_bytes': 25, 'sha256': 'a'*64}]}))
        (self.root/'edc/consumer/config.properties').write_text('web.http.management.auth.key=segreta\nedc.participant.id=museum_nl_01\n')

    def test_registro(self):
        entries = leggi_asset(self.root)
        self.assertEqual(len(entries), 1)

    def test_catalogo_lista(self):
        cat = {'dataset': [{'@id': 'rijksmuseum-sculture-10-opere-unificate',
                            'hasPolicy': [{'@id': 'offerta-123'}]}]}
        offers = estrai_offerte(cat)
        self.assertEqual(offerte := offers['rijksmuseum-sculture-10-opere-unificate'], ['offerta-123'])
        self.assertEqual(confronta(leggi_asset(self.root), offers)[0]['numero_offerte'], 1)

    def test_catalogo_oggetto(self):
        self.assertEqual(estrai_offerte({'dataset': {'@id': 'a', 'hasPolicy': {'@id': 'b'}}}), {'a': ['b']})

    def test_catalogo_vuoto(self):
        self.assertEqual(estrai_offerte({'dataset': []}), {})

    def test_doppione_bloccato(self):
        cat = {'dataset': [{'@id': 'x'}, {'@id': 'x'}]}
        with self.assertRaisesRegex(ValueError, 'ripetuto'):
            estrai_offerte(cat)

    def test_manifest_doppione_bloccato(self):
        source = self.root/'config/edc-assets.json'
        data = json.loads(source.read_text())
        data['assets'].append(dict(data['assets'][0]))
        source.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'duplicato'):
            leggi_asset(self.root)

    def test_api_non_locale_bloccata(self):
        with self.assertRaises(ValueError):
            ClientEDC('https://example.com/management/v4', 'token')

    def test_chiave_letta_non_esposta(self):
        self.assertEqual(leggi_chiave_consumer(self.root), 'segreta')

    def test_catalogo_vero_simulato_senza_modifiche(self):
        class Resp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{"dataset":[{"@id":"x","hasPolicy":{"@id":"offer-1"}}]}'
        with patch('edc_client.edc_api.apri', return_value=Resp()) as mocked:
            result = ClientEDC('http://127.0.0.1:41293/management/v4', 'segreta').richiesta_catalogo()
            sent = mocked.call_args.args[0]
            self.assertIsInstance(sent, Request)
            self.assertEqual(sent.get_method(), 'POST')
            self.assertEqual(json.loads(sent.data)['@type'], 'CatalogRequest')
            self.assertEqual(estrai_offerte(result), {'x': ['offer-1']})


if __name__ == '__main__': unittest.main()
