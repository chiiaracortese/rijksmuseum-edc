#!/usr/bin/env python3
"""Collaudo EDC: catalogo, negoziazione, trasferimento e integrità."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from bootstrap import ROOT, C, VOCAB, call, read_properties

PROVIDER_DSP = os.getenv(
    "EDC_PROVIDER_DSP",
    "http://provider:19194/protocol/2025-1"
)
PROTOCOL = "dataspace-protocol-http:2025-1"


def lista(valore):
    if valore is None:
        return []
    return valore if isinstance(valore, list) else [valore]


def campo(obj, nome):
    if not isinstance(obj, dict):
        return None
    for chiave, valore in obj.items():
        if chiave == nome or chiave.endswith(":" + nome):
            return valore
    return None


def stato_finale(api, tipo, identificativo, finali):
    precedente = None
    for _ in range(60):
        risultato = api(f"/{tipo}/{identificativo}")
        stato = campo(risultato, "state")

        if stato != precedente:
            print("  Stato:", stato)
            precedente = stato

        if stato in finali:
            return risultato

        time.sleep(2)

    raise RuntimeError(
        f"Tempo esaurito per {tipo}/{identificativo}. "
        "Controllare i log Docker prima di ripetere la richiesta."
    )


def verifica_ricezione(transfer_id, nome_file):
    """Non dichiara integrità verificata senza file e ricevuta."""
    impronta_id = hashlib.sha256(
        transfer_id.encode("utf-8")
    ).hexdigest()

    sorgente = ROOT / "data/rijksmuseum" / nome_file

    cartelle = [
        ROOT / "data/received/workflow" / impronta_id,
        Path("/received/workflow") / impronta_id,
    ]

    for cartella in cartelle:
        if not cartella.is_dir():
            continue

        ricevute = list(
            cartella.rglob("transfer-receipt.properties")
        )
        ricevuti = [
            p for p in cartella.rglob("*.json")
            if p.is_file()
        ]

        if not ricevute or len(ricevuti) != 1:
            continue

        if not sorgente.is_file():
            print("SHA-256: sorgente non accessibile")
            return False

        def sha256(percorso):
            return hashlib.sha256(
                percorso.read_bytes()
            ).hexdigest()

        atteso = sha256(sorgente)
        effettivo = sha256(ricevuti[0])

        print("SHA-256 sorgente:", atteso)
        print("SHA-256 ricevuto:", effettivo)

        if atteso == effettivo:
            print("INTEGRITÀ: file coincidenti")
            print("Ricevuta presente:", ricevute[0].name)
            return True

        print("INTEGRITÀ: HASH DIFFERENTI")
        return False

    print(
        "VERIFICA RICEZIONE: ricevuta o JSON non accessibile "
        "da questo container; verificare il Data Plane."
    )
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--asset",
        help="Identificativo della collezione da collaudare"
    )
    parser.add_argument(
        "--solo-catalogo",
        action="store_true",
        help="Esegue solo la discovery, senza negoziazioni"
    )
    parser.add_argument(
        "--trasferisci",
        action="store_true",
        help="Avvia il trasferimento solo dopo FINALIZED"
    )
    args = parser.parse_args()

    consumer = read_properties(
        ROOT / "edc/consumer/config.properties"
    )
    chiave = consumer["web.http.management.auth.key"]
    identita = consumer.get("edc.participant.id", "non specificata")

    def api(path, method="GET", data=None):
        return call(
            C, path, method=method,
            payload=data, key=chiave
        )

    assets = json.loads(
        (ROOT / "config/edc-assets.json").read_text(
            encoding="utf-8"
        )
    )["assets"]

    asset_id = args.asset or assets[0]["asset_id"]

    selezione = [
        a for a in assets if a["asset_id"] == asset_id
    ]

    if len(selezione) != 1:
        raise RuntimeError("Asset non presente nel registro")

    nome_file = Path(selezione[0]["filename"]).name

    if not (ROOT / "data/rijksmuseum" / nome_file).is_file():
        raise RuntimeError("JSON sorgente non trovato")

    print("Consumer configurato:", identita)
    print("Asset richiesto:", asset_id)

    print("\n1. DISCOVERY EDC")

    richiesta_catalogo = {
        "@context": {"@vocab": VOCAB},
        "@type": "CatalogRequest",
        "counterPartyId": "provider",
        "counterPartyAddress": PROVIDER_DSP,
        "protocol": PROTOCOL,
        "querySpec": {}
    }

    catalogo = api(
        "/catalog/request",
        "POST",
        richiesta_catalogo
    )

    datasets = lista(campo(catalogo, "dataset"))

    print("Dataset trovati:", len(datasets))

    selezionato = next(
        (
            d for d in datasets
            if d.get("@id") == asset_id
        ),
        None
    )

    if selezionato is None:
        raise RuntimeError(
            "La collezione Sculture non compare nel catalogo EDC"
        )

    offerte = lista(campo(selezionato, "hasPolicy"))
    if not offerte:
        raise RuntimeError(
            "Collezione trovata, ma senza offerte contrattuali"
        )

    offerta = offerte[0]
    offer_id = offerta.get("@id")
    if not offer_id:
        raise RuntimeError("L'offerta non contiene @id")

    print("Catalogo: OK")
    print("Offerta:", offer_id)

    if args.solo_catalogo:
        return

    print("\n2. NEGOZIAZIONE")

    policy = dict(offerta)
    policy["@context"] = ["http://www.w3.org/ns/odrl.jsonld", {"edc": VOCAB}]
    policy["@type"] = "Offer"
    policy["@id"] = offer_id
    policy["target"] = asset_id
    policy.setdefault("assigner", "provider")

    richiesta_contratto = {
        "@context": {"@vocab": VOCAB},
        "@type": "ContractRequest",
        "counterPartyId": "provider",
        "counterPartyAddress": PROVIDER_DSP,
        "protocol": PROTOCOL,
        "policy": policy
    }

    risposta = api(
        "/contractnegotiations",
        "POST",
        richiesta_contratto
    )

    negotiation_id = risposta["@id"]
    print("Negotiation ID:", negotiation_id)

    negoziazione = stato_finale(
        api, "contractnegotiations",
        negotiation_id, {"FINALIZED", "TERMINATED"}
    )

    stato = campo(negoziazione, "state")

    if stato == "TERMINATED":
        print("ACCESSO: RIFIUTATO")
        print(
            "Motivo:",
            campo(negoziazione, "errorDetail")
            or "Consultare il Provider"
        )
        print("Nessun trasferimento avviato.")
        return

    agreement_id = campo(
        negoziazione, "contractAgreementId"
    )

    if not agreement_id:
        raise RuntimeError(
            "FINALIZED senza Contract Agreement ID"
        )

    print("ACCESSO: AUTORIZZATO")
    print("Agreement ID:", agreement_id)

    if not args.trasferisci:
        print("Trasferimento non richiesto.")
        return

    print("\n3. TRASFERIMENTO EDC")

    richiesta_trasferimento = {
        "@context": {"@vocab": VOCAB},
        "@type": "TransferRequest",
        "assetId": asset_id,
        "contractId": agreement_id,
        "counterPartyId": "provider",
        "connectorId": "provider",
        "counterPartyAddress": PROVIDER_DSP,
        "protocol": PROTOCOL,
        "transferType": "HttpData-PULL"
    }

    risposta = api(
        "/transferprocesses",
        "POST",
        richiesta_trasferimento
    )

    transfer_id = risposta["@id"]
    print("Transfer Process ID:", transfer_id)

    trasferimento = stato_finale(
        api, "transferprocesses", transfer_id,
        {"STARTED", "COMPLETED", "TERMINATED"}
    )

    if campo(trasferimento, "state") == "TERMINATED":
        print("TRASFERIMENTO: TERMINATED")
        print(
            "Motivo:",
            campo(trasferimento, "errorDetail")
            or "Consultare i log"
        )
        return

    print("Transfer Process avviato.")
    print("STARTED non dimostra, da solo, la ricezione del JSON.")

    print("\n4. VERIFICA SHA-256")

    for tentativo in range(15):
        if verifica_ricezione(transfer_id, nome_file):
            print("COLLAUDO INTEGRITÀ: SUPERATO")
            return
        if tentativo < 14:
            time.sleep(2)

    print("COLLAUDO INTEGRITÀ: NON ANCORA CONFERMATO")


if __name__ == "__main__":
    try:
        main()
    except Exception as errore:
        raise SystemExit("ERRORE COLLAUDO: " + str(errore))
