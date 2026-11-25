#!/usr/bin/env python3
"""Verifica di riferimento per lo Scenario A della Fase 08.

Formula approvata: (R1 AND R2) OR R3. Le prove vengono caricate SOLO da
un registro locale sperimentale del Provider, mai dal payload del Consumer.
Non emette credenziali, non ne verifica firme crittografiche e non sostituisce
l'estensione Java/Policy Engine dell'EDC utilizzata nella Fase 10.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

R1_TYPE = "ExperimentalMuseumAccreditation"
R2_TYPE = "ExperimentalCulturalProjectAuthorization"
R3_TYPE = "ExperimentalHeritageProtectionMandate"
TYPES = (R1_TYPE, R2_TYPE, R3_TYPE)
PROJECT_TYPES = frozenset(("catalogazione", "digitalizzazione", "conservazione"))


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            return None
        return result.astimezone(timezone.utc)
    except ValueError:
        return None


def allowed_scope(attributes: dict, asset_id: str) -> bool:
    scope = attributes.get("asset_scope")
    return (isinstance(scope, list) and bool(scope)
            and all(isinstance(x, str) and x for x in scope)
            and asset_id in scope)


def validate_evidence(credential: object, kind: str, consumer_id: str, asset_id: str,
                      at: datetime, issuers: dict) -> bool:
    if not isinstance(credential, dict):
        return False
    if credential.get("type") != kind or credential.get("subject_id") != consumer_id:
        return False
    allowed = issuers.get(kind)
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) for x in allowed):
        return False
    if credential.get("issuer") not in allowed:
        return False
    if credential.get("revoked") is not False:
        return False
    start = parse_utc(credential.get("valid_from"))
    end = parse_utc(credential.get("valid_until"))
    if start is None or end is None or not start <= at < end:
        return False
    attr = credential.get("attributes")
    if not isinstance(attr, dict):
        return False

    if kind == R1_TYPE:
        return (attr.get("organization_type") == "museum"
                and attr.get("country_code") == "NL"
                and attr.get("accreditation_status") == "active")
    if kind == R2_TYPE:
        return (isinstance(attr.get("project_id"), str)
                and bool(attr["project_id"].strip())
                and attr.get("authorization_status") == "approved"
                and attr.get("project_type") in PROJECT_TYPES
                and allowed_scope(attr, asset_id))
    if kind == R3_TYPE:
        return (attr.get("organization_type") == "public_authority"
                and attr.get("mandate_type") == "cultural_heritage_protection"
                and attr.get("mandate_status") == "active"
                and allowed_scope(attr, asset_id))
    return False


def evaluate(request: object, provider_registry: object, at: datetime) -> dict:
    """Deny by default; registry is provided by Provider, never Consumer."""
    baseline = {
        "authorized": False, "R1": False, "R2": False, "R3": False,
        "rule": "(R1 AND R2) OR R3", "decision": "DENIED",
        "mode": "provider_local_experimental_registry_no_crypto",
    }
    if not isinstance(request, dict):
        return {**baseline, "reason": "Richiesta non valida"}
    consumer_id = request.get("consumer_id")
    asset_id = request.get("asset_id")
    if (not isinstance(consumer_id, str) or not consumer_id.strip()
            or not isinstance(asset_id, str) or not asset_id.strip()):
        return {**baseline, "reason": "Consumer o asset non identificati"}
    if not isinstance(provider_registry, dict):
        return {**baseline, "reason": "Registro Provider non disponibile"}
    issuers = provider_registry.get("trusted_issuers")
    attestations = provider_registry.get("attestations")
    if not isinstance(issuers, dict) or not isinstance(attestations, list):
        return {**baseline, "reason": "Registro Provider non valido"}
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        return {**baseline, "reason": "Istante di controllo non verificabile"}
    at = at.astimezone(timezone.utc)
    results = {
        kind: any(validate_evidence(a, kind, consumer_id, asset_id, at, issuers)
                  for a in attestations)
        for kind in TYPES
    }
    r1, r2, r3 = (results[k] for k in TYPES)
    authorized = (r1 and r2) or r3
    return {
        **baseline, "authorized": authorized,
        "R1": r1, "R2": r2, "R3": r3,
        "decision": "ALLOWED" if authorized else "DENIED",
        "reason": "Percorso valido" if authorized else "Nessun percorso completo e valido",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True,
                        help="File con consumer_id e asset_id: NO attestazioni autodefinite")
    parser.add_argument("--provider-registry", type=Path, required=True,
                        help="Registro delle attestazioni controllato dal Provider, NON quello del Consumer")
    parser.add_argument("--at", default=None,
                        help="Istante ISO8601 UTC o con offset; default ora UTC")
    args = parser.parse_args()
    at = datetime.now(timezone.utc) if args.at is None else parse_utc(args.at)
    if at is None:
        print(json.dumps({"authorized": False, "decision": "DENIED", "reason": "Timestamp non valido"}, indent=2))
        return 2
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        registry = json.loads(args.provider_registry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"authorized": False, "decision": "DENIED", "reason": f"Input non leggibile: {exc}"}, ensure_ascii=False, indent=2))
        return 2
    decision = evaluate(request, registry, at)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["authorized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
