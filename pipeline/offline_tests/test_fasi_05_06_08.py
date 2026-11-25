"""Test locali con esempi inventati e temporanei, non dati Rijksmuseum."""
from __future__ import annotations

import csv
import importlib.util
import io
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    path = PIPELINE_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mapping = load("fase05_local", "05_mappatura_semantica/valida_mappatura.py")
enrich = load("fase06_local", "06_arricchimento_semantico/valida_arricchimento.py")
access = load("fase08_local", "08_requisiti_uso/verifica_scenario_a.py")
AT = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
ASSET = "asset-sintetico-uno"
OTHER_ASSET = "asset-sintetico-due"
SUBJECT = "museo-fittizio"


def mapping_table():
    rows = [mapping.HEADERS]
    for name in mapping.FIELDS:
        prefix = "DERIVATA: trasformazione locale" if name == "production_date_summary" else "DIRETTA: selezione documentata"
        rows.append((name, "Descrizione sintetica del campo", prefix, "Corrispondenza da revisionare"))
    return rows


def original_data():
    return [{"object_uri": "https://example.invalid/oggetto-sintetico-1", "titles": "Oggetto inventato", "inventory_numbers": "TEST-1", "object_types": "simulato"}]


def enriched_data():
    return [{
        "object_uri": "https://example.invalid/oggetto-sintetico-1",
        "inventory_numbers": "TEST-1", "titles": "Oggetto inventato",
        "enriched_description": "A simulated object shown for a functional test, without any claim about a real artwork.",
        "source": {"organization": "Rijksmuseum", "url": "https://www.rijksmuseum.nl/en/collection/SYNTHETIC-DO-NOT-LOOK-UP", "language": "en"},
        "generation_method": "llm_enrichment_from_official_text",
        "source_evidence_summary": ["Example statement one", "Example statement two"],
        "review_status": "pending_human_review",
    }]


def cred(kind, subject=SUBJECT, asset=ASSET):
    attr = {
        access.R1_TYPE: {"organization_type": "museum", "country_code": "NL", "accreditation_status": "active"},
        access.R2_TYPE: {"project_id": "P-TEST", "authorization_status": "approved", "project_type": "catalogazione", "asset_scope": [asset]},
        access.R3_TYPE: {"organization_type": "public_authority", "mandate_type": "cultural_heritage_protection", "mandate_status": "active", "asset_scope": [asset]},
    }[kind]
    return {"type": kind, "subject_id": subject, "issuer": f"test-issuer-{kind}",
            "valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-01-01T00:00:00Z",
            "revoked": False, "attributes": attr}


def registry(proofs):
    return {"trusted_issuers": {kind: [f"test-issuer-{kind}"] for kind in access.TYPES},
            "attestations": list(proofs)}


def request(subject=SUBJECT, asset=ASSET):
    return {"consumer_id": subject, "asset_id": asset}


class Phase05Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fase05-sintetico-")
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "mappatura_sintetica.csv"

    def write_rows(self, rows):
        with self.file.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows(rows)

    def test_valid_25_row_four_column_mapping(self):
        self.write_rows(mapping_table())
        report = mapping.validate_mapping(self.file)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["record_count"], 25)
        self.assertEqual(report["scope"], "validazione_strutturale_non_semantica")

    def test_missing_field_denied(self):
        self.write_rows(mapping_table()[:-1])
        self.assertFalse(mapping.validate_mapping(self.file)["valid"])

    def test_out_of_order_denied(self):
        rows = mapping_table()
        rows[1], rows[2] = rows[2], rows[1]
        self.write_rows(rows)
        self.assertFalse(mapping.validate_mapping(self.file)["valid"])

    def test_fifth_column_denied(self):
        rows = mapping_table()
        rows[0] = (*rows[0], "imprevista")
        self.write_rows(rows)
        self.assertFalse(mapping.validate_mapping(self.file)["valid"])

    def test_summary_origin_must_be_derived(self):
        rows = mapping_table()
        rows[-1] = (*rows[-1][:2], "DIRETTA: errore simulato", rows[-1][3])
        self.write_rows(rows)
        self.assertFalse(mapping.validate_mapping(self.file)["valid"])

    def test_meaning_must_not_be_empty(self):
        rows = mapping_table()
        rows[1] = (rows[1][0], "", *rows[1][2:])
        self.write_rows(rows)
        self.assertFalse(mapping.validate_mapping(self.file)["valid"])


class Phase06Test(unittest.TestCase):
    def test_valid_structure_pending_human_review(self):
        report = enrich.validate_records(original_data(), enriched_data())
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(report["human_review_required"])
        self.assertEqual(report["external_source_actually_opened"], "NON_VERIFICABILE_OFFLINE")

    def test_reject_mismatched_original_identifier(self):
        new = enriched_data()
        new[0]["object_uri"] = "https://example.invalid/altro"
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_modified_inventory_number(self):
        new = enriched_data()
        new[0]["inventory_numbers"] = "ALTRO"
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_unofficial_url(self):
        new = enriched_data()
        new[0]["source"]["url"] = "https://rijksmuseum.nl.attacker.invalid/collection/1"
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_non_https_url(self):
        new = enriched_data()
        new[0]["source"]["url"] = "http://www.rijksmuseum.nl/en/collection/FAKE"
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_unapproved_review_status(self):
        new = enriched_data()
        new[0]["review_status"] = "approved"
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_extra_field(self):
        new = enriched_data()
        new[0]["confidence_score"] = 1.0
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_reject_more_than_10_records(self):
        base, new = [], []
        for i in range(11):
            o = original_data()[0].copy()
            r = enriched_data()[0].copy()
            o["object_uri"] += str(i)
            r["object_uri"] = o["object_uri"]
            base.append(o)
            new.append(r)
        self.assertFalse(enrich.validate_records(base, new)["valid"])

    def test_reject_duplicate_uris(self):
        new = enriched_data() + enriched_data()
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_two_languages_are_supported(self):
        new = enriched_data()
        new[0]["source"]["language"] = ["en", "nl"]
        self.assertTrue(enrich.validate_records(original_data(), new)["valid"])

    def test_no_evidence_is_rejected(self):
        new = enriched_data()
        new[0]["source_evidence_summary"] = []
        self.assertFalse(enrich.validate_records(original_data(), new)["valid"])

    def test_empty_enrichment_set_is_rejected(self):
        self.assertFalse(enrich.validate_records(original_data(), [])["valid"])


class Phase08Test(unittest.TestCase):
    def test_complete_boolean_truth_table(self):
        for a in (False, True):
            for b in (False, True):
                for c in (False, True):
                    proofs = [cred(kind) for enabled, kind in zip((a, b, c), access.TYPES) if enabled]
                    report = access.evaluate(request(), registry(proofs), AT)
                    self.assertEqual(report["authorized"], (a and b) or c, (a, b, c))

    def test_r1_and_r2_same_consumer(self):
        proofs = [cred(access.R1_TYPE), cred(access.R2_TYPE, subject="altra-identita")]
        self.assertFalse(access.evaluate(request(), registry(proofs), AT)["authorized"])

    def test_asset_scope_excludes_other_asset(self):
        proofs = [cred(access.R1_TYPE), cred(access.R2_TYPE, asset=ASSET)]
        self.assertFalse(access.evaluate(request(asset=OTHER_ASSET), registry(proofs), AT)["authorized"])

    def test_revoked_proof_not_valid(self):
        authority = cred(access.R3_TYPE)
        authority["revoked"] = True
        self.assertFalse(access.evaluate(request(), registry([authority]), AT)["authorized"])

    def test_unknown_issuer_denied(self):
        authority = cred(access.R3_TYPE)
        authority["issuer"] = "issuer-sconosciuto"
        self.assertFalse(access.evaluate(request(), registry([authority]), AT)["authorized"])

    def test_expired_proof_denied(self):
        authority = cred(access.R3_TYPE)
        authority["valid_until"] = "2025-01-01T00:00:00Z"
        self.assertFalse(access.evaluate(request(), registry([authority]), AT)["authorized"])

    def test_missing_project_id_denied(self):
        project = cred(access.R2_TYPE)
        project["attributes"]["project_id"] = " "
        self.assertFalse(access.evaluate(request(), registry([cred(access.R1_TYPE), project]), AT)["authorized"])

    def test_invalid_project_purpose_denied(self):
        project = cred(access.R2_TYPE)
        project["attributes"]["project_type"] = "scopo-non-previsto"
        self.assertFalse(access.evaluate(request(), registry([cred(access.R1_TYPE), project]), AT)["authorized"])

    def test_broken_r1_r2_does_not_block_r3(self):
        bad = cred(access.R1_TYPE)
        bad["revoked"] = True
        self.assertTrue(access.evaluate(request(), registry([bad, cred(access.R3_TYPE)]), AT)["authorized"])

    def test_missing_consumer_identity_denied(self):
        self.assertFalse(access.evaluate({"asset_id": ASSET}, registry([cred(access.R3_TYPE)]), AT)["authorized"])

    def test_malformed_date_denied(self):
        authority = cred(access.R3_TYPE)
        authority["valid_from"] = "2026-11-20"  # no timezone
        self.assertFalse(access.evaluate(request(), registry([authority]), AT)["authorized"])

    def test_registry_missing_denied(self):
        self.assertFalse(access.evaluate(request(), {"trusted_issuers": {}}, AT)["authorized"])

    def test_user_claims_not_used_as_provider_proof(self):
        incoming = request()
        incoming["self_claimed_R3"] = cred(access.R3_TYPE)
        self.assertFalse(access.evaluate(incoming, registry([]), AT)["authorized"])

    def test_r3_requires_mandate_type(self):
        authority = cred(access.R3_TYPE)
        authority["attributes"]["mandate_type"] = "qualcosaltro"
        self.assertFalse(access.evaluate(request(), registry([authority]), AT)["authorized"])

    def test_at_end_is_expired(self):
        authority = cred(access.R3_TYPE)
        self.assertFalse(access.evaluate(request(), registry([authority]),
                                         datetime(2027, 1, 1, tzinfo=timezone.utc))["authorized"])


if __name__ == "__main__":
    unittest.main()
