# Copyright (C) 2025 – SIB Swiss Institute of Bioinformatics.
#
# Derived and adapted from:
#   SPHN Connector / utils/validate_json.py
# The original file is distributed under the GNU General Public License v3.
# This adaptation is also distributed under GPL-3.0; see ../LICENSE.txt.
#
# Adaptation for the thesis prototype (2026):
# - validates Rijksmuseum arrays of 25-field object records, not patient files;
# - fixes SPHN's iter_errors generator success/failure test;
# - exits with 0 (success), 1 (nonconforming data), or 2 (execution error);
# - writes a structured JSON report without altering the input;
# - optionally checks a custom signed historical date-time format.

"""SPHN-derived JSON Schema validator for Rijksmuseum data (prototype v1)."""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

# Deliberately checks the SHAPE of a historical date-time, not historic calendar
# correctness (e.g., whether a month/day exists for a given historical year).
# Dates such as -0482-01-01T00:00:00Z occur in the Rijksmuseum records.
_HISTORICAL_DATE_TIME = re.compile(
    r"-?\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
    r"(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))\Z"
)


def date_time_checker(value: str) -> bool:
    """Adapted SPHN date_time_checker: supports negative years and full matches."""
    return isinstance(value, str) and bool(_HISTORICAL_DATE_TIME.fullmatch(value))


def _json_pointer(path_parts) -> str:
    def escape(part):
        return str(part).replace('~', '~0').replace('/', '~1')
    return ''.join('/' + escape(part) for part in path_parts) or '/'


def validate_data(schema_file: str, data_file: str, check_formats: bool,
                  report_file: str | None = None, max_saved_errors: int = 100) -> int:
    """Validate data using SPHN's jsonschema approach; return 0, 1 or 2."""
    report = {
        'tool': 'Rijksmuseum prototype validator adapted from SPHN Connector',
        'source_component': 'SPHN Connector / utils/validate_json.py',
        'schema_file': str(schema_file),
        'data_file': str(data_file),
        'format_checks_enabled': bool(check_formats),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'total_records': None,
        'invalid_records': 0,
        'total_validation_errors': 0,
        'reported_errors': [],
        'valid': False,
        'status': 'error',
    }
    status_code = 2
    try:
        with open(schema_file, encoding='utf-8') as stream:
            schema = json.load(stream)
        with open(data_file, encoding='utf-8') as stream:
            data = json.load(stream)
        # A malformed *schema* is different from a non-conforming *dataset*.
        Draft202012Validator.check_schema(schema)

        formats = None
        if check_formats:
            formats = FormatChecker()
            formats.checkers['historical-date-time'] = (date_time_checker, ())
        validator = Draft202012Validator(schema, format_checker=formats)

        if isinstance(data, list):
            report['total_records'] = len(data)
        invalid_indices = set()
        root_level_errors = 0
        for err in validator.iter_errors(data):
            report['total_validation_errors'] += 1
            path = list(err.absolute_path)
            if path and isinstance(path[0], int):
                invalid_indices.add(path[0])
            else:
                root_level_errors += 1
            if len(report['reported_errors']) < max_saved_errors:
                report['reported_errors'].append({
                    'json_pointer': _json_pointer(path),
                    'message': err.message,
                    'rule': err.validator,
                })
        report['invalid_records'] = len(invalid_indices)
        report['root_level_errors'] = root_level_errors
        report['valid'] = (report['total_validation_errors'] == 0)
        report['status'] = 'valid' if report['valid'] else 'invalid'
        status_code = 0 if report['valid'] else 1
        logging.info('Validation %s: %s record(s), %s error(s).',
                     report['status'], report['total_records'],
                     report['total_validation_errors'])
        for err in report['reported_errors'][:10]:
            logging.warning('%s: %s', err['json_pointer'], err['message'])
        if report['total_validation_errors'] > 10:
            logging.warning('Further errors are summarized in the JSON report.')
    except Exception as exc:
        report['status'] = 'error'
        report['execution_error'] = f'{type(exc).__name__}: {exc}'
        logging.error('Validation could not be completed: %s', report['execution_error'])
    finally:
        if report_file:
            try:
                destination = Path(report_file)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
            except OSError as exc:
                logging.error('Cannot write report: %s', exc)
                status_code = 2
    return status_code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SPHN-derived JSON Schema validator for Rijksmuseum')
    parser.add_argument('schema_file', help='Path to a JSON Schema file')
    parser.add_argument('data_file', help='Path to the input JSON array')
    parser.add_argument('-f', '--check_formats', action='store_true',
                        help='Enable URI and custom historical-date-time validation (recommended)')
    parser.add_argument('--report', help='Write structured report to this JSON path')
    parser.add_argument('--max-saved-errors', type=int, default=100,
                        help='Maximum number of error examples in the report (default: 100)')
    arguments = parser.parse_args()
    if arguments.max_saved_errors < 0:
        parser.error('--max-saved-errors must be >= 0')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    sys.exit(validate_data(arguments.schema_file, arguments.data_file,
                           arguments.check_formats, arguments.report,
                           arguments.max_saved_errors))
