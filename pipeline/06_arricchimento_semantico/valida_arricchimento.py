#!/usr/bin/env python3
"""Valida gli arricchimenti descrittivi LLM separati dai JSON a 25 campi.

Il controllo e' LOCALE e STRUTTURALE: l'URL viene controllato come dominio,
non viene visitato. Nessuna evidenza viene dichiarata verificata online;
qualita' linguistica, fondamento delle affermazioni e revisione restano umani.
Non produce testo mediante LLM e non modifica il dataset originale.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = frozenset({
    "object_uri", "inventory_numbers", "titles", "enriched_description",
    "source", "generation_method", "source_evidence_summary", "review_status",
})
SOURCE_FIELDS = frozenset({"organization", "url", "language"})
ALLOWED_HOSTS = frozenset({"rijksmuseum.nl", "www.rijksmuseum.nl"})


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def records_in(value: object, label: str) -> list:
    """Support list, single object or a single documented array wrapper."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for wrapper in ("enrichments", "arricchimenti", "records"):
            if wrapper in value and isinstance(value[wrapper], list):
                return value[wrapper]
        if label == "arricchimento" and "object_uri" in value:
            return [value]
    raise ValueError(f"{label}: attesa una lista di oggetti (o involucro con array 'records'/'enrichments'/'arricchimenti')")


def official_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme.lower() == "https" and
                (parsed.hostname or "").lower() in ALLOWED_HOSTS and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and bool(parsed.path.strip("/")))
    except ValueError:
        return False


def validate_records(original: object, enrichments: object) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        base = records_in(original, "dataset normalizzato")
        new = records_in(enrichments, "arricchimento")
    except ValueError as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": [],
                "normalized_count": 0, "enrichment_count": 0,
                "method": "controllo_strutturale_offline"}
    by_uri: dict[str, dict] = {}
    for index, item in enumerate(base):
        if not isinstance(item, dict) or not nonempty(item.get("object_uri")):
            errors.append(f"Dataset originale, record {index+1}: object_uri mancante")
            continue
        uri = item["object_uri"]
        if uri in by_uri:
            errors.append(f"Dataset normalizzato: object_uri duplicato (record {index+1})")
        by_uri[uri] = item

    if not 1 <= len(new) <= 10:
        errors.append(f"Arricchimenti: attesi da 1 a 10 record, trovati {len(new)}")

    seen: set[str] = set()
    word_counts: list[int] = []
    language_counts = {"en": 0, "nl": 0, "en+nl": 0}
    for index, item in enumerate(new):
        loc = f"Arricchimento {index+1}"
        if not isinstance(item, dict):
            errors.append(f"{loc}: record non oggetto")
            continue
        if set(item) != FIELDS:
            errors.append(f"{loc}: schema non corrispondente agli otto campi approvati (mancanti={sorted(FIELDS-set(item))}, aggiunti={sorted(set(item)-FIELDS)})")
        uri = item.get("object_uri")
        if not nonempty(uri):
            errors.append(f"{loc}: object_uri mancante")
            continue
        if uri in seen:
            errors.append(f"{loc}: object_uri duplicato")
        seen.add(uri)
        matched = by_uri.get(uri)
        if matched is None:
            errors.append(f"{loc}: object_uri non presente nel JSON normalizzato")
        else:
            for field in ("inventory_numbers", "titles"):
                if item.get(field) != matched.get(field):
                    errors.append(f"{loc}: {field} non identico al record normalizzato")

        for field in ("inventory_numbers", "titles", "enriched_description"):
            if not nonempty(item.get(field)):
                errors.append(f"{loc}: {field} deve essere una stringa non vuota")
        description = item.get("enriched_description")
        if nonempty(description):
            words = len(description.split())
            word_counts.append(words)
            if not 100 <= words <= 150:
                warnings.append(f"{loc}: lunghezza {words} parole, fuori dalla fascia indicativa 100–150; la fedeltà alla fonte prevale")

        if item.get("generation_method") != "llm_enrichment_from_official_text":
            errors.append(f"{loc}: generation_method non conforme")
        if item.get("review_status") != "pending_human_review":
            errors.append(f"{loc}: review_status deve essere pending_human_review")

        evidence = item.get("source_evidence_summary")
        if not isinstance(evidence, list) or not evidence or not all(nonempty(v) for v in evidence):
            errors.append(f"{loc}: source_evidence_summary deve contenere evidenze testuali non vuote")
        elif len(evidence) < 2:
            warnings.append(f"{loc}: presente una sola evidenza; documentarne almeno due se disponibili")

        source = item.get("source")
        if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
            errors.append(f"{loc}: source non presenta i tre campi approvati")
            continue
        if source.get("organization") != "Rijksmuseum":
            errors.append(f"{loc}: source.organization non e' Rijksmuseum")
        url = source.get("url")
        if not nonempty(url) or not official_url(url):
            errors.append(f"{loc}: URL non appartenente a una pagina HTTPS del dominio ufficiale Rijksmuseum")
        language = source.get("language")
        if language == "en":
            language_counts["en"] += 1
        elif language == "nl":
            language_counts["nl"] += 1
        elif language == ["en", "nl"]:
            language_counts["en+nl"] += 1
        else:
            errors.append(f"{loc}: source.language non conforme (en, nl, ['en','nl'])")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "normalized_count": len(base),
        "enrichment_count": len(new),
        "word_count": {
            "min": min(word_counts) if word_counts else None,
            "max": max(word_counts) if word_counts else None,
            "average": round(sum(word_counts)/len(word_counts), 2) if word_counts else None,
        },
        "source_language_counts": language_counts,
        "method": "controllo_strutturale_offline",
        "human_review_required": True,
        "external_source_actually_opened": "NON_VERIFICABILE_OFFLINE",
        "factual_faithfulness": "NON_VERIFICABILE_AUTOMATICAMENTE",
        "note": "Non prova consultazione web, corrispondenza della scheda, accuratezza visiva o assenza di allucinazioni.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized", required=True, type=Path, help="JSON normalizzato, fuori repository")
    parser.add_argument("--enrichments", required=True, type=Path, help="JSON di arricchimenti, fuori repository")
    args = parser.parse_args()
    try:
        base = json.loads(args.normalized.read_text(encoding="utf-8"))
        new = json.loads(args.enrichments.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({"valid": False, "errors": [f"Lettura JSON fallita: {exc}"]}, ensure_ascii=False, indent=2))
        return 1
    report = validate_records(base, new)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
