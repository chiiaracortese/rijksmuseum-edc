#!/usr/bin/env python3
"""Fase 7 — metadati/provenance per macrocategorie Rijksmuseum.

Il modello e' JSON locale, ispirato a DCAT 3 e PROV-O, non RDF/JSON-LD.
Funziona con la sola cartella/ZIP di arricchimento (test parziale) e,
se forniti, con i 14 JSON normalizzati (metadati di integrita' effettivi).
Non modifica mai gli input. Non attribuisce diritti, pubblicazioni o review
non documentati.
"""
import argparse
import collections
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "arricchimento_semantico_"
SUFFIX = ".json"


def sha256_file_and_count_objects(path):
    """Hash e conteggio degli oggetti al primo livello di un array JSON.

    Scansione a memoria costante; e' un conteggio strutturale, NON una
    nuova convalida JSON Schema (la validazione appartiene alla fase 4).
    """
    digest = hashlib.sha256()
    n = 0
    arrays = 0
    objects = 0
    in_string = False
    escaped = False
    begun = False
    ended = False
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
            for b in chunk:
                if in_string:
                    if escaped:
                        escaped = False
                    elif b == 92:  # backslash
                        escaped = True
                    elif b == 34:  # quote
                        in_string = False
                    continue
                if b == 34:
                    in_string = True
                elif b == 91:  # [
                    if ended:
                        raise ValueError("Caratteri dopo l'array JSON")
                    arrays += 1
                    begun = True
                elif b == 93:  # ]
                    arrays -= 1
                    if arrays < 0:
                        raise ValueError("Array JSON non bilanciato")
                    if arrays == 0:
                        ended = True
                elif b == 123:  # {
                    if arrays == 1 and objects == 0:
                        n += 1
                    objects += 1
                elif b == 125:  # }
                    objects -= 1
                    if objects < 0:
                        raise ValueError("Oggetti JSON non bilanciati")
                elif not begun and b not in b" \t\n\r":
                    raise ValueError("Il dataset non e' un array JSON")
                elif ended and b not in b" \t\n\r":
                    raise ValueError("Caratteri dopo la fine dell'array JSON")
    if not begun or not ended or objects or arrays or in_string:
        raise ValueError("Struttura incompleta nel dataset JSON")
    return digest.hexdigest(), path.stat().st_size, n


def read_enrichments(path):
    """Trova i 14 JSON nell'archivio esterno o nella cartella estratta.

    Le copie nei piccoli ZIP interni non sono usate: si prende una sola
    versione dal JSON espanso nell'archivio principale.
    """
    p = Path(path)
    data = {}
    if p.is_file() and p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            candidates = [(Path(n).name, z.read(n), n) for n in z.namelist()
                          if n.endswith(".json") and "__MACOSX" not in n]
    elif p.is_dir():
        candidates = [(file.name, file.read_bytes(), str(file)) for file in p.rglob("*.json")
                      if "__MACOSX" not in str(file)]
    else:
        raise ValueError("--arricchimento richiede uno ZIP o una cartella")
    for basename, raw, origin in candidates:
        if not (basename.startswith(PREFIX) and basename.endswith(SUFFIX)):
            continue
        category = basename[len(PREFIX):-len(SUFFIX)]
        if category in data:
            raise ValueError("File duplicati per la categoria: " + category)
        records = json.loads(raw)
        if not isinstance(records, list):
            raise ValueError("Il JSON arricchito deve essere un array: " + basename)
        uris = [r.get("object_uri") for r in records]
        if not all(isinstance(u, str) and u.startswith("https://") for u in uris):
            raise ValueError("object_uri mancante/non valido: " + basename)
        if len(set(uris)) != len(uris):
            raise ValueError("object_uri duplicati: " + basename)
        if not all(isinstance(r.get("enriched_description"), str)
                   and r["enriched_description"].strip() for r in records):
            raise ValueError("Descrizione arricchita mancante: " + basename)
        status = collections.Counter(r.get("review_status", "non_indicato") for r in records)
        methods = sorted(set(r.get("generation_method", "non_indicato") for r in records))
        sources = sorted(set(r.get("source", {}).get("organization", "non_indicata") for r in records))
        urls = sorted({r["source"]["url"] for r in records
                       if isinstance(r.get("source"), dict)
                       and isinstance(r["source"].get("url"), str)})
        languages = set()
        for r in records:
            lang = r.get("source", {}).get("language")
            if isinstance(lang, str):
                languages.add(lang)
            elif isinstance(lang, list):
                languages.update(str(x) for x in lang)
        data[category] = {
            "nome": basename,
            "dimensione_byte": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "records": records,
            "conteggio": len(records),
            "status": dict(sorted(status.items())),
            "methods": methods,
            "sources": sources,
            "urls": urls,
            "languages": sorted(languages),
            "origin": origin,
        }
    if not data:
        raise ValueError("Non sono stati trovati JSON di arricchimento")
    return data



# Indicatore specifico, verificato sui 14 report della fase 6. Il numero
# estratto dai report non equivale a una nuova lettura del dataset normalizzato.
PATTERN_CONTEGGI_REPORT = {
    "armi_oggetti_militari_visivo": r"Oggetti nel JSON originale:\s*\*{0,2}([\d.]+)",
    "ceramiche_porcellane": r"Oggetti presenti nel dataset:\s*\*{0,2}([\d.]+)",
    "dipinti_e_pitture": r"Oggetti complessivi:\s*\*{0,2}([\d.]+)",
    "fotografia": r"Oggetti totali:\s*\*{0,2}([\d.]+)",
    "gioielli_accessori": r"Oggetti nel dataset:\s*\*{0,2}([\d.]+)",
    "libri_documenti": r"\|\s*Record originali\s*\|\s*([\d.]+)",
    "mobili_arredi": r"Oggetti nel dataset:\s*\*{0,2}([\d.]+)",
    "modelli_manufatti_tecnici": r"\*\*Oggetti nel dataset:\*\*\s*([\d.]+)",
    "monete_medaglie": r"Totale record:\s*\*{0,2}([\d.]+)",
    "oggetti_vetro": r"Oggetti totali:\s*\*{0,2}([\d.]+)",
    "sculture": r"Dataset elaborato:.*?\(([\d.]+) record",
    "stampe": r"Oggetti originali:\s*\*{0,2}([\d.]+)",
    "strumenti_scientifici_musicali": r"Record originali:\s*\*{0,2}([\d.]+)",
    "tessuti_abbigliamento": r"\|\s*Oggetti nel dataset originale\s*\|\s*([\d.]+)",
}


def read_report_counts(path):
    """Legge i conteggi storici dei dataset dai Markdown dello ZIP/cartella.

    Non valida i numeri: vengono riportati come dichiarati dalla fase 6.
    """
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            candidates = [(name, z.read(name).decode("utf-8")) for name in z.namelist()
                          if "/report_" in name and name.endswith(".md") and "__MACOSX" not in name]
    else:
        candidates = [(str(f), f.read_text(encoding="utf-8")) for f in path.rglob("report_*.md")]
    output = {}
    for category, pattern in PATTERN_CONTEGGI_REPORT.items():
        matching = [(name, body) for name, body in candidates if
                    f"/arricchimento_semantico_{category}/report_" in name.replace("\\", "/")]
        if len(matching) > 1:
            raise ValueError(f"Report di arricchimento duplicati per {category}")
        if not matching:
            continue
        name, body = matching[0]
        found = re.search(pattern, body, flags=re.IGNORECASE)
        if not found:
            continue
        number = int(found.group(1).strip(".").replace(".", ""))
        output[category] = (number, Path(name).name)
    return output


def find_normalized(input_dir, category):
    if not input_dir:
        return None
    root = Path(input_dir)
    if not root.is_dir():
        raise FileNotFoundError("Cartella dataset inesistente: " + str(root))
    candidates = list(root.rglob(f"rijksmuseum_{category}_25_campi*.json"))
    if len(candidates) > 1:
        raise ValueError("File normalizzati ambigui (seleziona una sola versione): " + ", ".join(map(str, candidates)))
    return candidates[0] if candidates else None


def make_card(category, enrich, normalized_path=None, storico=None, fonte_storico=None,
              esito_validazione=None, segnalazioni=None):
    if normalized_path:
        digest, size, count = sha256_file_and_count_objects(normalized_path)
        count_source = "conteggio_calcolato_sul_file_normalizzato"
        count_verified = True
        normal_state = "file_letto"
        normal_file = normalized_path.name
    else:
        digest, size, count = None, None, storico
        count_source = fonte_storico if storico is not None else None
        count_verified = False
        normal_state = "file_non_disponibile_in_questa_esecuzione"
        normal_file = f"rijksmuseum_{category}_25_campi.json"

    normal_id = f"rijksmuseum_{category}_25_campi"
    enriched_id = f"arricchimento_semantico_{category}"
    methods = enrich["methods"]
    return {
        "versione_modello": "fase7_test_v1",
        "tipo_documento": "scheda_metadati_e_provenance",
        "avvertenza_standard": "Modello JSON locale ispirato a DCAT 3 e PROV-O; non e' una serializzazione RDF/JSON-LD.",
        "data_generazione_scheda_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "identificativo_locale": normal_id,
            "titolo": f"Rijksmuseum — {category.replace('_', ' ').capitalize()}",
            "macrocategoria": category,
            "descrizione": f"Dataset normalizzato di oggetti museali Rijksmuseum per la macrocategoria {category.replace('_', ' ')}; schema comune di 25 campi.",
            "fonte_dati_originali": "Rijksmuseum",
            "file_csv_intermedio_documentato": "rijksmuseum_completo.csv",
            "numero_oggetti": count,
            "origine_numero_oggetti": count_source,
            "conteggio_verificato_sul_json_nel_test": count_verified,
            "numero_campi_per_oggetto_documentato": 25,
            "schema_documentato": "schema_25_campi.json",
            "mappatura_semantica_documentata": "semantic_mapping_rijksmuseum_25_campi_revisione_01.csv",
            "validazione_tecnica_precedentemente_documentata": {
                "esito": esito_validazione,
                "segnalazioni_da_revisionare": segnalazioni,
                "rieseguita_in_questa_fase": False,
            },
        },
        "distribuzione": {
            "dataset_normalizzato": {
                "identificativo_locale": normal_id,
                "nome_file": normal_file,
                "formato": "JSON",
                "mime_type": "application/json",
                "stato_file": normal_state,
                "dimensione_byte": size,
                "sha256": digest,
                "url_accesso": None,
                "licenza_della_distribuzione": None,
            },
            "risorsa_derivata_arricchimento": {
                "identificativo_locale": enriched_id,
                "tipo_relazione": "risorsa_derivata_distinta_dal_dataset_normalizzato",
                "nome_file": enrich["nome"],
                "formato": "JSON",
                "mime_type": "application/json",
                "dimensione_byte": enrich["dimensione_byte"],
                "sha256": enrich["sha256"],
                "numero_descrizioni_arricchite": enrich["conteggio"],
                "chiave_di_collegamento": "object_uri",
                "lingue_delle_fonti": enrich["languages"],
                "stati_revisione": enrich["status"],
                "url_accesso": None,
                "licenza_della_distribuzione": None,
            },
        },
        "provenance_dataset": {
            "origine_documentata": "Rijksmuseum",
            "file_intermedio_documentato": "rijksmuseum_completo.csv",
            "attivita_precedenti_documentate": [
                {"fase": "acquisizione_e_normalizzazione", "descrizione": "Acquisizione dal Rijksmuseum e normalizzazione dal CSV al modello comune di 25 campi", "data_storica": None},
                {"fase": "profiling", "descrizione": "Analisi delle caratteristiche dei dataset normalizzati", "data_storica": None},
                {"fase": "validazione", "descrizione": "Controlli strutturali e tecnici sui dataset normalizzati", "data_storica": None},
                {"fase": "semantic_mapping", "descrizione": "Documentazione delle corrispondenze dei campi con Linked Art", "data_storica": None},
            ],
            "arricchimento_semantico": {
                "tipo_attivita": "generazione_descrizioni_descrittive_assistita_da_llm",
                "metodi_dichiarati_nei_record": methods,
                "numero_record_risultanti": enrich["conteggio"],
                "risorsa_di_partenza": normal_id,
                "risorsa_generata": enriched_id,
                "fonte_testuale_organizzazioni": enrich["sources"],
                "url_fonti_ufficiali_presenti_nei_record": enrich["urls"],
                "chiave_collegamento_ai_dati_originali": "object_uri",
                "stati_revisione_dichiarati": enrich["status"],
                "revisione_umana_completata": (False if any(s in enrich["status"] for s in ("pending_human_review", "non_indicato")) else None),
                "nome_e_versione_modello_llm": None,
                "data_storica_esecuzione": None,
                "nota": "I testi sono contenuti derivati e non dati originali certificati dal museo.",
            },
        },
        "pubblicazione": {
            "stato": "non_documentata_come_pubblicata_nel_dataspace",
            "endpoint_dataspace": None,
            "url_catalogo": None,
            "editore_del_data_product": None,
            "data_acquisizione_originale": None,
            "licenza_e_condizioni_uso": None,
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Fase 7 Rijksmuseum: metadati del dataset e dell'arricchimento")
    p.add_argument("--arricchimento", required=True, help="ZIP principale o cartella estratta della fase 6")
    p.add_argument("--input-dir", help="Cartella dei JSON normalizzati a 25 campi")
    p.add_argument("--output-dir", required=True, help="Cartella per le schede generate")
    p.add_argument("--solo", help="Genera solo la macrocategoria indicata")
    p.add_argument("--numero-oggetti-storico", type=int, help="Solo per --solo; numero dal report precedente, non verificato in questa esecuzione")
    p.add_argument("--fonte-conteggio-storico", help="Solo per --solo; nome del report da cui viene il conteggio")
    p.add_argument("--esito-validazione-documentato", help="Solo per --solo; esito del precedente report")
    p.add_argument("--segnalazioni-documentate", type=int, help="Solo per --solo; segnalazioni dal precedente report")
    args = p.parse_args(argv)
    if not args.solo and any(x is not None for x in (args.numero_oggetti_storico, args.fonte_conteggio_storico,
                                                      args.esito_validazione_documentato, args.segnalazioni_documentate)):
        p.error("I parametri storici specifici richiedono --solo")
    if args.numero_oggetti_storico is not None and args.numero_oggetti_storico < 0:
        p.error("Il conteggio storico deve essere non negativo")
    enrichments = read_enrichments(args.arricchimento)
    reports = read_report_counts(args.arricchimento)
    selected = [args.solo] if args.solo else sorted(enrichments)
    if any(cat not in enrichments for cat in selected):
        p.error("Macrocategoria non presente nello ZIP di arricchimento")
    output = Path(args.output_dir)
    (output / "metadati").mkdir(parents=True, exist_ok=True)
    summaries = []
    for cat in selected:
        norm = find_normalized(args.input_dir, cat)
        if args.input_dir and norm is None:
            raise FileNotFoundError(f"File normalizzato non trovato per: {cat}")
        storico, fonte_storico = reports.get(cat, (None, None))
        if args.solo and args.numero_oggetti_storico is not None:
            storico, fonte_storico = args.numero_oggetti_storico, args.fonte_conteggio_storico
        card = make_card(cat, enrichments[cat], norm, storico,
                         fonte_storico, args.esito_validazione_documentato,
                         args.segnalazioni_documentate)
        card["provenance_dataset"]["arricchimento_semantico"]["report_metodologico_fase6"] = reports.get(cat, (None, None))[1]
        target = output / "metadati" / f"metadati_{cat}.json"
        target.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summaries.append({"categoria": cat,
                          "conteggio_da_report_fase6": storico,
                          "numero_oggetti_normalizzati": card["dataset"]["numero_oggetti"],
                          "numero_arricchiti": card["distribuzione"]["risorsa_derivata_arricchimento"]["numero_descrizioni_arricchite"],
                          "json_normalizzato_disponibile": norm is not None,
                          "scheda": str(target.relative_to(output))})
        print(f"Generato: {target}")
    summary = {"fase": 7, "macrocategorie_analizzate": len(summaries),
               "totale_oggetti_da_report_fase6": sum(x["conteggio_da_report_fase6"] or 0 for x in summaries),
               "totale_descrizioni_arricchite": sum(x["numero_arricchiti"] for x in summaries),
               "categorie": summaries,
               "nota": "Schede JSON locali ispirate a DCAT 3 e PROV-O; solo valori disponibili o documentati."}
    (output / "riepilogo_fase7.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        sys.exit(1)
