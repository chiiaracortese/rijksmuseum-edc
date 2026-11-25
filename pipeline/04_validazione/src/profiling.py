# Rijksmuseum thesis prototype 2026: new component; profiling is not from SPHN source.
"""Read-only profiling for an array of museum JSON records.

Profiling describes completeness; absence does not itself imply invalidity.
"""
from collections import Counter
from datetime import datetime, timezone


def value_present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def json_type(value):
    if value is None: return 'null'
    if isinstance(value, bool): return 'boolean'
    if isinstance(value, dict): return 'object'
    if isinstance(value, list): return 'array'
    if isinstance(value, str): return 'string'
    if isinstance(value, int): return 'integer'
    if isinstance(value, float): return 'number'
    return type(value).__name__


def profile_data(data, expected_fields):
    if not isinstance(data, list):
        raise TypeError('Si attende un array JSON di oggetti')
    per_field = {}
    for field in expected_fields:
        found = 0; present = 0; types = Counter()
        for record in data:
            if not isinstance(record, dict) or field not in record:
                continue
            found += 1
            value = record[field]
            types[json_type(value)] += 1
            present += int(value_present(value))
        per_field[field] = {
            'records_with_field': found,
            'records_with_nonempty_value': present,
            'records_with_empty_value': found-present,
            'records_missing_field': len(data)-found,
            'completeness_pct': round(100*present/len(data), 2) if data else None,
            'json_types': dict(types),
        }
    extra = Counter()
    malformed_record_indices = []
    for index, record in enumerate(data):
        if not isinstance(record,dict):
            malformed_record_indices.append(index)
            continue
        extra.update(set(record)-set(expected_fields))
    identifiers = [record.get('object_uri') for record in data if isinstance(record,dict)
                   and isinstance(record.get('object_uri'),str) and record.get('object_uri')]
    return {
        'component':'Profiling JSON museale (nuovo modulo, non codice SPHN)',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'record_count':len(data), 'expected_field_count':len(expected_fields),
        'non_object_record_indices':malformed_record_indices[:25],
        'non_object_record_count':len(malformed_record_indices),
        'nonexpected_field_occurrences':dict(extra),
        'nonempty_object_uri_count':len(identifiers),
        'distinct_nonempty_object_uri_count':len(set(identifiers)),
        'field_stats':per_field,
        'note':'Profiling descrittivo: vuoto non equivale automaticamente a errore; stringhe speciali quali anonymous e unknown non sono rimosse.'
    }
