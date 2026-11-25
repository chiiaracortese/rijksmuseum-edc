"""Test offline 01, 02, 03, 07, 09 con dati interamente sintetici.

Esecuzione dalla radice della repository:
  python -m unittest discover -s pipeline/offline_tests -v

La suite NON utilizza file museali, servizi di rete, né modifica i sorgenti.
"""
from __future__ import annotations

import csv
import io
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[2]
INGESTION = REPO / "pipeline/01_ingestion/estrai_rijksmuseum_csv.py"
CORE = REPO / "pipeline/02_normalizzazione/macrocategorie_25_campi/macrocategorie_core_14.py"
PROFILING = REPO / "pipeline/03_profiling/profiling.py"
METADATA = REPO / "pipeline/07_metadati/genera_metadati_fase7.py"
POLICY = REPO / "pipeline/09_policy_odrl/genera_policy_fase9.py"


def module_from_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Sorgente non importabile: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def as_json(obj):
    return json.dumps(obj, ensure_ascii=False)


def nt_uri(uri):
    return f"<{uri}>"


def sample_chunk(number, object_uri, item_type, title):
    """Triplette di fantasia: nessun record o URI di un'opera del museo."""
    crm = "http://www.cidoc-crm.org/cidoc-crm/"
    p1 = nt_uri(crm + "P1_is_identified_by")
    p2 = nt_uri(crm + "P2_has_type")
    symbolic = nt_uri(crm + "P190_has_symbolic_content")
    rdf_type = nt_uri("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    type_app = nt_uri(crm + "E33_E41_Linguistic_Appellation")
    label = nt_uri("http://www.w3.org/2000/01/rdf-schema#label")
    node = f"_:syntheticTitle{number}"
    # Il record e la classificazione sono dati sintetici prodotti al volo.
    triples = [
        f"{nt_uri(object_uri)} {p1} {node} .",
        f"{node} {rdf_type} {type_app} .",
        f"{node} {symbolic} {json.dumps(title)}@en .",
        f"{node} {symbolic} {json.dumps('Titel ' + str(number))}@nl .",
        f"{nt_uri(object_uri)} {p2} {nt_uri(item_type)} .",
        f"{nt_uri(item_type)} {label} {json.dumps('Synthetic type')}@en .",
    ]
    return ("\n".join(triples) + "\n").encode("utf-8")


class SyntheticPipelineTests(unittest.TestCase):
    """Verifica le funzioni originali tramite input e output temporanei."""

    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="rijksmuseum-offline-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.root = Path(cls.workspace.name)
        cls.ing = module_from_file("rijksmuseum_ingestion_test", INGESTION)
        cls.normal = module_from_file("rijksmuseum_core_test", CORE)
        cls.prof = module_from_file("rijksmuseum_profiling_test", PROFILING)
        cls.meta = module_from_file("rijksmuseum_metadata_test", METADATA)
        cls.policy = module_from_file("rijksmuseum_policy_test", POLICY)

        cls.synthetic_dataset = cls.root / "synthetic_rdf"
        rdf = cls.synthetic_dataset / "rdf"
        rdf.mkdir(parents=True)
        cls.painting_uri = "https://synthetic.example/objects/P1"
        cls.sculpture_uri = "https://synthetic.example/objects/S1"
        cls.painting_type = "https://synthetic.example/types/painting"
        cls.sculpture_type = "https://synthetic.example/types/sculpture"
        for n, uri, kind, title in (
            (1, cls.painting_uri, cls.painting_type, "Synthetic Painting"),
            (2, cls.sculpture_uri, cls.sculpture_type, "Synthetic Sculpture"),
        ):
            prefix = rdf / f"objects-{n:06d}"
            with gzip.open(prefix.with_suffix(".nt.gz"), "wb") as handle:
                handle.write(sample_chunk(n, uri, kind, title))
            prefix.with_suffix(".json").write_text(
                as_json({"accepted": 1, "source_records": [[uri, "accepted"]]}),
                encoding="utf-8",
            )

        cls.csv_path = cls.root / "synthetic_intermediate.csv"
        result = cls.run_ingestion("--dataset", str(cls.synthetic_dataset), "--output", str(cls.csv_path))
        if result.returncode != 0:
            raise AssertionError("Ingestion fallita:\n" + result.stdout + result.stderr)
        with cls.csv_path.open(encoding="utf-8-sig", newline="") as handle:
            cls.csv_records = list(csv.DictReader(handle))

        mapping = {cat: [] for cat in cls.normal.FILE_NAMES}
        mapping["dipinti_e_pitture"] = [{"uri": cls.painting_type}]
        mapping["sculture"] = [{"uri": cls.sculpture_type}]
        cls.mapping_file = cls.root / "mapping_synthetic.json"
        cls.mapping_file.write_text(as_json({"categories": mapping, "generic_vessels": []}), encoding="utf-8")
        cls.normalized_dir = cls.root / "normalized_synthetic"
        with patch.object(cls.normal, "MAPPING_FILE", cls.mapping_file), redirect_stdout(io.StringIO()):
            cls.normal.run(("dipinti_e_pitture", "sculture"), [
                "--input", str(cls.csv_path), "--output-dir", str(cls.normalized_dir)
            ])
        cls.paintings = json.loads((cls.normalized_dir / cls.normal.FILE_NAMES["dipinti_e_pitture"]).read_text(encoding="utf-8"))
        cls.sculptures = json.loads((cls.normalized_dir / cls.normal.FILE_NAMES["sculture"]).read_text(encoding="utf-8"))

        # Genera il materiale sintetico della Fase 06 solo nella directory temporanea.
        cls.enrichment_zip = cls.root / "synthetic_enrichment.zip"
        with ZipFile(cls.enrichment_zip, "w") as archive:
            for category in cls.normal.PRIORITY:
                entries = [{
                    "object_uri": f"https://synthetic.example/enrich/{category}",
                    "enriched_description": "Testo inventato per il test automatico.",
                    "generation_method": "synthetic_unit_test",
                    "review_status": "pending_human_review",
                    "source": {"organization": "Synthetic test fixture", "language": "it"},
                }]
                archive.writestr(f"arricchimento_semantico_{category}.json", as_json(entries))
        cls.meta_out = cls.root / "phase7_outputs"
        with redirect_stdout(io.StringIO()):
            # Il generatore resta quello originale, i file sono temporanei.
            rc = cls.meta.main(["--arricchimento", str(cls.enrichment_zip),
                                "--output-dir", str(cls.meta_out)])
        if rc != 0:
            raise AssertionError("Fase 07 sintetica non completata")
        cls.phase7_summary = json.loads((cls.meta_out / "riepilogo_fase7.json").read_text(encoding="utf-8"))
        cls.policy_root = cls.root / "phase9_outputs"
        inputs = cls.policy_root / "input_fase8"
        inputs.mkdir(parents=True)
        spec = {
            "access_expression": "(R1 AND R2) OR R3",
            "requirements": [{"id": req, "claims": [f"synthetic_{req}_claim"]} for req in ("R1", "R2", "R3")],
        }
        (inputs / "specifica_scenario_A.json").write_text(as_json(spec), encoding="utf-8")
        (inputs / "riepilogo_fase7.json").write_text(as_json(cls.phase7_summary), encoding="utf-8")
        with patch.object(cls.policy, "ROOT", cls.policy_root):
            cls.manifest = cls.policy.build()

    @classmethod
    def run_ingestion(cls, *args):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, str(INGESTION), *args],
                              capture_output=True, text=True, timeout=30, env=env)

    def test_01_ingestion_creates_two_rows_with_15_columns(self):
        self.assertEqual(len(self.csv_records), 2)
        self.assertEqual(set(self.csv_records[0]), set(self.ing.COLUMNS))
        self.assertEqual([r["object_uri"] for r in self.csv_records],
                         [self.painting_uri, self.sculpture_uri])

    def test_02_ingestion_preserves_titles_and_types(self):
        names = json.loads(self.csv_records[0]["titles"])
        self.assertIn({"value": "Synthetic Painting", "lang": "en"}, names)
        classifications = json.loads(self.csv_records[0]["object_types"])
        self.assertEqual(classifications[0]["uri"], self.painting_type)

    def test_03_ingestion_max_files_and_only_uri(self):
        sample = self.root / "sample_one_chunk.csv"
        result = self.run_ingestion("--dataset", str(self.synthetic_dataset),
                                    "--output", str(sample), "--max-files", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        with sample.open(encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)
        picked = self.root / "picked_object.csv"
        result = self.run_ingestion("--dataset", str(self.synthetic_dataset),
                                    "--output", str(picked), "--only-uri", self.sculpture_uri)
        self.assertEqual(result.returncode, 0, result.stderr)
        with picked.open(encoding="utf-8-sig") as f:
            self.assertEqual([x["object_uri"] for x in csv.DictReader(f)], [self.sculpture_uri])

    def test_04_ingestion_refuses_to_replace_existing_csv(self):
        original = self.csv_path.read_bytes()
        result = self.run_ingestion("--dataset", str(self.synthetic_dataset),
                                    "--output", str(self.csv_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.csv_path.read_bytes(), original)

    def test_05_normalization_produces_exactly_25_fields(self):
        self.assertEqual(len(self.paintings), 1)
        self.assertEqual(len(self.sculptures), 1)
        for row in self.paintings + self.sculptures:
            self.assertEqual(tuple(row), self.normal.FIELDS)
            self.assertEqual(len(row), 25)

    def test_06_normalization_english_title_and_disjoint_categories(self):
        self.assertEqual(self.paintings[0]["titles"], "Synthetic Painting")
        self.assertEqual(self.sculptures[0]["titles"], "Synthetic Sculpture")
        self.assertNotEqual(self.paintings[0]["object_uri"], self.sculptures[0]["object_uri"])
        self.assertEqual(self.paintings[0]["alternative_titles"], [])

    def test_07_normalization_rejects_existing_outputs(self):
        with patch.object(self.normal, "MAPPING_FILE", self.mapping_file), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.normal.run(("sculture",), ["--input", str(self.csv_path),
                                 "--output-dir", str(self.normalized_dir)])

    def test_08_profiling_counts_empty_and_missing(self):
        records = [self.paintings[0], {"object_uri": "https://synthetic.example/missing"}]
        result = self.prof.profile_data(records, list(self.normal.FIELDS))
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["field_stats"]["titles"]["records_missing_field"], 1)
        self.assertEqual(result["field_stats"]["titles"]["records_with_nonempty_value"], 1)
        self.assertEqual(result["distinct_nonempty_object_uri_count"], 2)

    def test_09_profiling_rejects_non_array_input(self):
        with self.assertRaises(TypeError):
            self.prof.profile_data({"not": "an array"}, ["titles"])

    def test_10_phase7_creates_14_cards_without_original_jsons(self):
        self.assertEqual(self.phase7_summary["macrocategorie_analizzate"], 14)
        self.assertEqual(self.phase7_summary["totale_descrizioni_arricchite"], 14)
        self.assertTrue(all(x["numero_oggetti_normalizzati"] is None
                            for x in self.phase7_summary["categorie"]))
        first = json.loads((self.meta_out / "metadati/metadati_dipinti_e_pitture.json").read_text(encoding="utf-8"))
        self.assertFalse(first["dataset"]["conteggio_verificato_sul_json_nel_test"])
        self.assertEqual(first["distribuzione"]["risorsa_derivata_arricchimento"]["numero_descrizioni_arricchite"], 1)

    def test_11_phase7_calculates_actual_sha256_of_synthetic_normalization(self):
        file = self.normalized_dir / self.normal.FILE_NAMES["dipinti_e_pitture"]
        digest, size, count = self.meta.sha256_file_and_count_objects(file)
        self.assertEqual(count, 1)
        self.assertEqual(size, file.stat().st_size)
        self.assertEqual(digest, hashlib.sha256(file.read_bytes()).hexdigest())
        enrichment = self.meta.read_enrichments(self.enrichment_zip)["dipinti_e_pitture"]
        card = self.meta.make_card("dipinti_e_pitture", enrichment, normalized_path=file)
        self.assertEqual(card["dataset"]["numero_oggetti"], 1)
        self.assertTrue(card["dataset"]["conteggio_verificato_sul_json_nel_test"])
        self.assertEqual(card["distribuzione"]["dataset_normalizzato"]["sha256"], digest)

    def test_12_phase7_rejects_duplicate_synthetic_uris(self):
        bad = self.root / "duplicate_enrichment.zip"
        same = {"object_uri": "https://synthetic.example/duplicate", "enriched_description": "Prova"}
        with ZipFile(bad, "w") as archive:
            archive.writestr("arricchimento_semantico_sculture.json", as_json([same, same]))
        with self.assertRaisesRegex(ValueError, "duplicati"):
            self.meta.read_enrichments(bad)

    def test_13_phase9_generates_14_policies_and_contract_templates(self):
        self.assertEqual(len(self.manifest), 14)
        self.assertEqual(len({x["edc_asset_id_proposto"] for x in self.manifest}), 14)
        for row in self.manifest:
            offer = json.loads((self.policy_root / row["offerta_odrl"]).read_text(encoding="utf-8"))
            contract = json.loads((self.policy_root / row["contratto_edc_bozza"]).read_text(encoding="utf-8"))
            self.assertEqual(offer["@type"], "odrl:Offer")
            self.assertTrue(offer["odrl:permission"][0]["odrl:target"]["@id"].endswith("/" + row["edc_asset_id_proposto"]))
            self.assertEqual(contract["assetsSelector"][0]["operandRight"], row["edc_asset_id_proposto"])

    def test_14_phase9_boolean_truth_table(self):
        offer = json.loads((self.policy_root / "policies_odrl/offer_dipinti_e_pitture.jsonld").read_text(encoding="utf-8"))
        expr = offer["odrl:permission"][0]["odrl:constraint"]

        def eval_expression(node, claims):
            if "odrl:or" in node:
                return any(eval_expression(c, claims) for c in node["odrl:or"]["@list"])
            if "odrl:and" in node:
                return all(eval_expression(c, claims) for c in node["odrl:and"]["@list"])
            left = node["odrl:leftOperand"]["@id"].rsplit("/", 1)[-1]
            return claims[left] is node["odrl:rightOperand"]["@value"]

        allowed_count = 0
        for r1, r2, r3 in itertools.product((False, True), repeat=3):
            claims = {self.policy.RKEY["R1"]: r1, self.policy.RKEY["R2"]: r2,
                      self.policy.RKEY["R3"]: r3}
            expected = (r1 and r2) or r3
            self.assertEqual(eval_expression(expr, claims), expected)
            allowed_count += int(expected)
        self.assertEqual(allowed_count, 5)

    def test_15_phase9_edc_template_contains_same_boolean_structure(self):
        template = json.loads((self.policy_root / "edc_templates/policy_scenario_A_negoziazione.json").read_text(encoding="utf-8"))
        condition = template["policy"]["permission"][0]["constraint"]
        self.assertEqual(len(condition["or"]), 2)
        self.assertEqual([x["leftOperand"] for x in condition["or"][0]["and"]],
                         [self.policy.RKEY["R1"], self.policy.RKEY["R2"]])
        self.assertEqual(condition["or"][1]["leftOperand"], self.policy.RKEY["R3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
