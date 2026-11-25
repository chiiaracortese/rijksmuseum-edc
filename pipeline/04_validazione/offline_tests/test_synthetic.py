"""Verifiche offline su dati sintetici generati in directory temporanee.

Questi test esercitano il codice reale della Fase 04 ma NON sostituiscono
lo schema ufficiale a 25 campi, i controlli su 951 record né i test storici.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from profiling import profile_data
from run_pipeline import run
from run_prechecks import execute_checks
from validate_json import validate_data

# Schema minimo SOLO per i test offline; non è lo schema di produzione a 25 campi.
DATE_LIST = {"type": "array", "minItems": 1,
             "items": {"type": "string", "format": "historical-date-time"}}
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "items": {
        "type": "object",
        "required": ["object_uri", "titles", "production_dates",
                     "sets", "equivalent_uris"],
        "additionalProperties": False,
        "properties": {
            "object_uri": {"type": "string", "format": "uri"},
            "titles": {"type": "string"},
            "production_dates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "minProperties": 1,
                    "additionalProperties": False,
                    "properties": {
                        "earliest_start": DATE_LIST,
                        "latest_end": DATE_LIST,
                    },
                },
            },
            "sets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["uri"],
                    "properties": {"uri": {"type": "string", "format": "uri"}},
                },
            },
            "equivalent_uris": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
            },
        },
    },
}

CONFIG = {
    "iri_fields": ["object_uri", "sets[].uri", "equivalent_uris[]"],
    "regex_rules": [
        {"id": "object_uri_shape", "field": "object_uri",
         "regex": r"https?://[^\s]+"}
    ],
    "max_examples_per_rule": 5,
}


def record(index):
    """Crea record inventati; nessuna informazione sulle opere Rijksmuseum."""
    return {
        "object_uri": f"https://example.org/synthetic/objects/{index}",
        "titles": f"Oggetto sintetico {index}",
        "production_dates": [
            {"earliest_start": ["1857-01-01T00:00:00Z"],
             "latest_end": ["1857-12-31T23:59:59Z"]}
        ],
        "sets": [{"uri": "https://example.org/synthetic/sets/one"}],
        "equivalent_uris": [f"https://example.org/synthetic/equivalent/{index}"],
    }


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class OfflineSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="rijks-fase04-offline-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.schema_path = save(self.root / "schema_test.json", SCHEMA)
        self.config_path = save(self.root / "prechecks_test.json", CONFIG)
        self.records = [record(1), record(2)]

    def execute(self, data):
        data_path = save(self.root / "synthetic.json", data)
        before = hashlib.sha256(data_path.read_bytes()).hexdigest()
        code, summary = run(
            data_path, self.schema_path, self.config_path,
            self.root / "reports"
        )
        self.assertEqual(before, hashlib.sha256(data_path.read_bytes()).hexdigest(),
                         "Il runner non deve modificare l'input")
        return code, summary

    def test_clean_workflow_and_reports(self):
        code, summary = self.execute(self.records)
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["status"], "checks_passed")
        self.assertTrue(summary["input_unchanged"])
        self.assertEqual(summary["stage_results"]["ingestion"]["records"], 2)
        self.assertEqual(summary["stage_results"]["profiling"]["fields_profiled"], 5)
        self.assertEqual(summary["stage_results"]["validation"]["total_errors"], 0)
        self.assertEqual(summary["stage_results"]["prechecks"]["blocking_findings"], 0)
        for name in ["profiling.json", "validazione_schema.json",
                     "prechecks.json", "riepilogo_pipeline.json"]:
            self.assertTrue((self.root / "reports" / name).exists(), name)

    def test_wrong_uri_is_blocked(self):
        bad = copy.deepcopy(self.records)
        bad[0]["object_uri"] = "non un uri"
        code, summary = self.execute(bad)
        self.assertEqual(code, 1, summary)
        self.assertEqual(summary["status"], "blocked")
        self.assertGreater(
            summary["stage_results"]["prechecks"]["blocking_findings"], 0)

    def test_duplicate_uri_is_blocked(self):
        bad = copy.deepcopy(self.records)
        bad[1]["object_uri"] = bad[0]["object_uri"]
        code, summary = self.execute(bad)
        self.assertEqual(code, 1, summary)
        self.assertGreater(summary["stage_results"]["prechecks"]["blocking_findings"], 0)

    def test_unexpected_field_is_blocked(self):
        bad = copy.deepcopy(self.records)
        bad[0]["unapproved_property"] = "test"
        code, summary = self.execute(bad)
        self.assertEqual(code, 1, summary)
        self.assertGreater(summary["stage_results"]["validation"]["total_errors"], 0)

    def test_inverted_year_is_review_only(self):
        data = copy.deepcopy(self.records[:1])
        data[0]["production_dates"] = [
            {"earliest_start": ["1911-01-01T00:00:00Z"],
             "latest_end": ["1910-12-31T23:59:59Z"]}
        ]
        code, summary = self.execute(data)
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary["review_status"], "pending")
        self.assertEqual(summary["stage_results"]["prechecks"]["review_findings"], 1)

    def test_partial_date_is_informational(self):
        data = copy.deepcopy(self.records[:1])
        data[0]["production_dates"] = [
            {"earliest_start": ["1857-01-01T00:00:00Z"]}
        ]
        code, summary = self.execute(data)
        self.assertEqual(code, 0, summary)
        self.assertEqual(
            summary["stage_results"]["prechecks"]["informational_findings"], 1)

    def test_negative_historical_year_is_accepted(self):
        data = copy.deepcopy(self.records[:1])
        data[0]["production_dates"] = [
            {"earliest_start": ["-0482-01-01T00:00:00Z"],
             "latest_end": ["-0482-12-31T23:59:59Z"]}
        ]
        file_path = save(self.root / "bce.json", data)
        report_path = self.root / "validation_report.json"
        self.assertEqual(
            validate_data(str(self.schema_path), str(file_path), True,
                          str(report_path)), 0)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["total_validation_errors"], 0)

    def test_empty_date_object_is_rejected(self):
        data = copy.deepcopy(self.records[:1])
        data[0]["production_dates"] = [{}]
        code, summary = self.execute(data)
        self.assertEqual(code, 1, summary)
        self.assertGreater(summary["stage_results"]["validation"]["total_errors"], 0)

    def test_nested_invalid_uri(self):
        bad = copy.deepcopy(self.records[:1])
        bad[0]["sets"][0]["uri"] = "http://bad host"
        result = execute_checks(bad, CONFIG, "synthetic.json")
        self.assertGreater(result["summary"]["blocking_findings"], 0)

    def test_profiler_tracks_missing_or_empty_fields(self):
        bad = copy.deepcopy(self.records)
        bad[0]["titles"] = ""
        bad[1].pop("titles")
        profile = profile_data(bad, list(SCHEMA["items"]["required"]))
        stats = profile["field_stats"]["titles"]
        self.assertEqual(stats["records_with_empty_value"], 1)
        self.assertEqual(stats["records_missing_field"], 1)


if __name__ == "__main__":
    unittest.main()
