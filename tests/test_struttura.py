import json, unittest, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Struttura(unittest.TestCase):
    def test_single_service_data_plane(self):
        s=(ROOT/'compose.yaml').read_text()
        self.assertIn('  data-plane:',s)
        self.assertNotIn('consumer-data-plane:',s)
        self.assertNotIn('data-source:',s)
    def test_java_single_entrypoint(self):
        folder=ROOT/'edc/data-plane/src/main/java/org/rijksmuseum/dataspace/dataplane'
        mains=list(folder.glob('*Main.java'))
        self.assertEqual(len(mains),1)
        self.assertIn('.onStarted(ricezione)', mains[0].read_text())
        self.assertIn('.onStart(esposizione)', mains[0].read_text())
    def test_registries(self):
        assets=json.loads((ROOT/'config/edc-assets.json').read_text())['assets']
        self.assertEqual(len(assets), 14)
        self.assertEqual(len({a['asset_id'] for a in assets}), 14)
        self.assertIn('rijksmuseum-sculture-10-opere-unificate',
                      {a['asset_id'] for a in assets})
        registro=json.loads((ROOT/'config/attestazioni.json').read_text())['registry']
        self.assertIn('museum_nl_01',registro)
        self.assertIn('university_it_01',registro)
    def test_flow_bindings(self):
        s=(ROOT/'scripts/bootstrap.py').read_text()
        self.assertEqual(s.count("register_dataplane(P,kp,'rijksmuseum-shared-dataplane'"),1)
        self.assertEqual(s.count("register_dataplane(C,kc,'rijksmuseum-shared-dataplane'"),1)
    def test_removed_nginx(self):
        s=(ROOT/'edc/data-plane/src/main/java/org/rijksmuseum/dataspace/dataplane/RijksmuseumOnStart.java').read_text()
        self.assertNotIn('HttpRequest backendRequest',s)
        self.assertIn('Files.newInputStream(file)',s)
    def test_identity_link(self):
        i=(ROOT/'edc/control-plane/policy-functions/src/main/java/org/eclipse/edc/sample/extension/policy/IamClaimsExtension.java').read_text()
        c=(ROOT/'edc/control-plane/policy-functions/src/main/java/org/eclipse/edc/sample/extension/policy/ScenarioConstraintFunction.java').read_text()
        self.assertIn('"client_id"',i)
        self.assertIn('"client_id"',c)
if __name__ == '__main__': unittest.main()
