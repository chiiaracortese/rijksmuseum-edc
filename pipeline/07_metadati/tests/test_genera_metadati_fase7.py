import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import genera_metadati_fase7 as m


class TestGenerator(unittest.TestCase):
    def test_read_enrichment_and_sample_card(self):
        with tempfile.TemporaryDirectory() as t:
            zpath = Path(t) / "a.zip"
            objects = [{"object_uri": "https://id.rijksmuseum.nl/1", "enriched_description": "A description",
                        "generation_method": "llm_enrichment_from_official_text",
                        "source": {"organization": "Rijksmuseum", "url": "https://www.rijksmuseum.nl/a", "language": "en"},
                        "review_status": "pending_human_review"}]
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("arricchimento semantico/arricchimento_semantico_dipinti_e_pitture/x.json", "[]")
                z.writestr("arricchimento semantico/arricchimento_semantico_dipinti_e_pitture/arricchimento_semantico_dipinti_e_pitture.json", json.dumps(objects))
            enrich = m.read_enrichments(zpath)["dipinti_e_pitture"]
            card = m.make_card("dipinti_e_pitture", enrich, storico=5345, fonte_storico="report_precedente")
            self.assertEqual(card["dataset"]["numero_oggetti"], 5345)
            self.assertIsNone(card["distribuzione"]["dataset_normalizzato"]["sha256"])
            self.assertEqual(card["distribuzione"]["risorsa_derivata_arricchimento"]["stati_revisione"]["pending_human_review"], 1)

    def test_normalized_streaming_count_and_hash(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "rijksmuseum_dipinti_e_pitture_25_campi.json"
            p.write_text('[{"one": "a [ brace { and escape \\\""}, {"child": [{"x": 1}]}, {}]', encoding="utf-8")
            sha, size, n = m.sha256_file_and_count_objects(p)
            self.assertEqual(n, 3)
            self.assertEqual(size, p.stat().st_size)
            self.assertEqual(len(sha), 64)

    def test_report_count_from_zip(self):
        with tempfile.TemporaryDirectory() as t:
            zpath = Path(t) / "reports.zip"
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("arricchimento semantico/arricchimento_semantico_dipinti_e_pitture/report_arricchimento_visivo_dipinti_e_pitture.md", "Oggetti complessivi: **5345**")
            counts = m.read_report_counts(zpath)
            self.assertEqual(counts["dipinti_e_pitture"], (5345, "report_arricchimento_visivo_dipinti_e_pitture.md"))

    def test_report_count_not_interpreted_as_new_dataset_read(self):
        enrich = {"nome":"arricchimento_semantico_stampe.json", "dimensione_byte":2,
                  "sha256":"0"*64, "conteggio":10, "languages":["en"],
                  "status":{"pending_human_review":10}, "methods":["llm_enrichment_from_official_text"],
                  "sources":["Rijksmuseum"], "urls":[]}
        card = m.make_card("stampe", enrich, storico=407657, fonte_storico="report_stampe.md")
        self.assertEqual(card["dataset"]["numero_oggetti"], 407657)
        self.assertFalse(card["dataset"]["conteggio_verificato_sul_json_nel_test"])
        self.assertIsNone(card["distribuzione"]["dataset_normalizzato"]["sha256"])

    def test_duplicate_uris_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "arricchimento_semantico_dipinti_e_pitture.json"
            r = {"object_uri": "https://id.rijksmuseum.nl/1", "enriched_description": "x"}
            p.write_text(json.dumps([r, r]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicati"):
                m.read_enrichments(t)


if __name__ == "__main__":
    unittest.main()
