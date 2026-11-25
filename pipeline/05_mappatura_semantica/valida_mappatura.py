#!/usr/bin/env python3
"""Controllo strutturale del CSV a quattro colonne della mappatura approvata.

Questo programma NON crea corrispondenze Linked Art e NON ne certifica
la correttezza ontologica: quella rimane una decisione umana documentata.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

HEADERS = (
    "campo_json", "significato_locale", "origine", "corrispondenza_linked_art"
)
FIELDS = (
    "object_uri", "inventory_numbers", "titles", "descriptions", "dimensions",
    "credit_line", "object_types", "support", "materials", "creators",
    "production_places", "current_locations", "production_dates",
    "visual_item_uris", "sets", "equivalent_uris", "alternative_titles",
    "object_description", "technical_description", "additional_dimensions",
    "inscriptions", "provenance", "related_object_notes",
    "production_techniques", "production_date_summary",
)
ORIGIN_PATTERN = re.compile(r"^(DIRETTA|DERIVATA)(?:\s*[:;—–-]\s*|\s+)(\S.*)$", re.DOTALL)


def validate_mapping(path: Path) -> dict:
    """Return machine-readable structural report; never rewrite source file."""
    errors: list[str] = []
    origin_counts = {"DIRETTA": 0, "DERIVATA": 0}
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        reader = csv.reader(text.splitlines(keepends=True), strict=True)
        rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return {"valid": False, "errors": [f"Impossibile leggere il CSV: {exc}"],
                "record_count": 0, "origin_counts": origin_counts,
                "scope": "validazione_strutturale_non_semantica"}

    if not rows:
        errors.append("CSV vuoto")
    elif tuple(rows[0]) != HEADERS:
        errors.append("Intestazioni non corrispondenti alle quattro colonne approvate e al loro ordine")

    records = rows[1:] if rows else []
    if len(records) != len(FIELDS):
        errors.append(f"Numero di righe errato: {len(records)} (atteso {len(FIELDS)})")

    for index, row in enumerate(records):
        if len(row) != len(HEADERS):
            errors.append(f"Riga dati {index+1}: trovate {len(row)} colonne, attese quattro")
            continue
        field, meaning, origin, linked = [value.strip() for value in row]
        if index < len(FIELDS) and field != FIELDS[index]:
            errors.append(f"Riga dati {index+1}: campo inatteso o fuori ordine ({field!r})")
        if not meaning:
            errors.append(f"Riga dati {index+1}: significato_locale vuoto")
        if not linked:
            errors.append(f"Riga dati {index+1}: corrispondenza_linked_art vuota")
        match = ORIGIN_PATTERN.fullmatch(origin)
        if not match:
            errors.append(f"Riga dati {index+1}: origine priva di DIRETTA/DERIVATA e spiegazione")
        else:
            origin_counts[match.group(1)] += 1
            if field == "production_date_summary" and match.group(1) != "DERIVATA":
                errors.append("production_date_summary deve risultare DERIVATA")

    if len({row[0] for row in records if row}) != len(records):
        errors.append("Uno o più campo_json risultano duplicati")

    return {
        "valid": not errors,
        "errors": errors,
        "record_count": len(records),
        "origin_counts": origin_counts,
        "sha256_csv": hashlib.sha256(raw).hexdigest(),
        "scope": "validazione_strutturale_non_semantica",
        "manual_review_required": [
            "verificare tutte le corrispondenze Linked Art/AAT sul materiale approvato",
            "non confondere corrispondenza concettuale e percorso RDF osservato",
            "non considerare le etichette testuali come URI RDF originali",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping_csv", type=Path, help="CSV approvato a quattro colonne; non incluso nella repository")
    args = parser.parse_args()
    result = validate_mapping(args.mapping_csv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
