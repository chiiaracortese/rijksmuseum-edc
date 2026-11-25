"""Small integration tests for the SPHN-derived JSON validator (stdlib only)."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'src' / 'validate_json.py'
SCHEMA = ROOT / 'schemas' / 'schema_25_campi.json'
INPUT = ROOT / 'input' / 'rijksmuseum_strumenti_scientifici_musicali_25_campi.json'
VALID = ROOT / 'examples' / 'esempio_valido.json'
INVALID = ROOT / 'examples' / 'esempio_con_errori.json'


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(path):
    with tempfile.TemporaryDirectory() as folder:
        report_file = Path(folder) / 'result.json'
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(SCHEMA), str(path), '-f', '--report', str(report_file)],
            text=True, capture_output=True, check=False,
        )
        return proc, json.loads(report_file.read_text(encoding='utf-8'))


class TestValidation(unittest.TestCase):
    def test_original_951_records_are_structurally_conformant_and_unchanged(self):
        original_digest = checksum(INPUT)
        proc, report = run_case(INPUT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report['total_records'], 951)
        self.assertEqual(report['total_validation_errors'], 0)
        self.assertEqual(report['status'], 'valid')
        self.assertEqual(checksum(INPUT), original_digest)

    def test_three_valid_examples(self):
        proc, report = run_case(VALID)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report['total_records'], 3)

    def test_three_intentional_errors_are_detected(self):
        proc, report = run_case(INVALID)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report['total_records'], 3)
        self.assertEqual(report['invalid_records'], 3)
        self.assertEqual(report['total_validation_errors'], 3)
        self.assertEqual(report['status'], 'invalid')
        self.assertIn('/2/production_dates/0/earliest_start/0',
                      [err['json_pointer'] for err in report['reported_errors']])

    def test_negative_historical_year_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            record = json.loads(VALID.read_text(encoding='utf-8'))[0]
            record['production_dates'] = [{
                'earliest_start': ['-0482-01-01T00:00:00Z'],
                'latest_end': ['-0482-12-31T23:59:59Z'],
            }]
            path = Path(folder) / 'bce_date.json'
            path.write_text(json.dumps([record]), encoding='utf-8')
            proc, report = run_case(path)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(report['total_validation_errors'], 0)


    def test_partial_date_is_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            record = json.loads(VALID.read_text(encoding='utf-8'))[0]
            for dates in (
                [{'earliest_start':['1857-01-01T00:00:00Z']}],
                [{'latest_end':['0100-12-31T23:59:59Z']}],
            ):
                record['production_dates'] = dates
                p = Path(folder) / 'partial.json'
                p.write_text(json.dumps([record]),encoding='utf-8')
                proc, report = run_case(p)
                self.assertEqual(proc.returncode,0,report)
                self.assertEqual(report['total_validation_errors'],0)

    def test_empty_date_object_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            record = json.loads(VALID.read_text(encoding='utf-8'))[0]
            for dates in ([{}],[{'earliest_start':[]}],[{'latest_end':[]}]):
                record['production_dates'] = dates
                p = Path(folder) / 'empty.json'
                p.write_text(json.dumps([record]),encoding='utf-8')
                proc, report = run_case(p)
                self.assertEqual(proc.returncode,1,report)
                self.assertGreater(report['total_validation_errors'],0)

if __name__ == '__main__':
    unittest.main()
