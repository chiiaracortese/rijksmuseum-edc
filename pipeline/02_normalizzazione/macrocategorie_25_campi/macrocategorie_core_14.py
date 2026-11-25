#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motore comune per 14 esportatori Rijksmuseum (5 precedenti + 9 nuovi).

Legge rijksmuseum_completo.csv in streaming e produce JSON con 25 campi.
Usa il medesimo schema a 25 campi e le stesse cinque regole di classificazione
dei primi estrattori. Le nove categorie aggiunte vengono dopo quelle originali.

REQUISITI: Python 3.9+; nessun modulo da installare.

La mappa locale di URI (mappatura_macrocategorie.json) e' costruita dal file
rijksmuseum_tipologie_complete.csv fornito dall'utente. Non pretende di essere
una tassonomia ufficiale, ne' di classificare gli oltre 800.000 oggetti.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

FOLDER = Path.home() / "Desktop" / "macrocategorie json"
INPUT_CSV = Path.home() / "Desktop" / "rijksmuseum_completo.csv"
MAPPING_FILE = Path(__file__).with_name("mappatura_macrocategorie_14.json")

# Precedenza stabile. Le cinque categorie originali mantengono identico ordine
# rispetto al pacchetto precedente, quindi gli output gia' creati NON
# compariranno anche nelle nuove nove categorie. Le nuove nove si escludono a vicenda.
OLD_PRIORITY = (
    "fotografie", "monete_medaglie", "dipinti_e_pitture", "sculture", "stampe"
)
NEW_PRIORITY = (
    "armi_oggetti_militari", "gioielli_accessori",
    "strumenti_scientifici_musicali", "oggetti_vetro", "ceramiche_porcellane",
    "tessuti_abbigliamento", "mobili_arredi", "libri_documenti",
    "modelli_manufatti_tecnici",
)
PRIORITY = OLD_PRIORITY + NEW_PRIORITY
FILE_NAMES = {
    "stampe": "rijksmuseum_stampe_25_campi.json",
    "fotografie": "rijksmuseum_fotografie_25_campi.json",
    "dipinti_e_pitture": "rijksmuseum_dipinti_e_pitture_25_campi.json",
    "monete_medaglie": "rijksmuseum_monete_medaglie_25_campi.json",
    "sculture": "rijksmuseum_sculture_25_campi.json",
    "ceramiche_porcellane": "rijksmuseum_ceramiche_porcellane_25_campi.json",
    "tessuti_abbigliamento": "rijksmuseum_tessuti_abbigliamento_25_campi.json",
    "libri_documenti": "rijksmuseum_libri_documenti_25_campi.json",
    "mobili_arredi": "rijksmuseum_mobili_arredi_25_campi.json",
    "oggetti_vetro": "rijksmuseum_oggetti_vetro_25_campi.json",
    "strumenti_scientifici_musicali": "rijksmuseum_strumenti_scientifici_musicali_25_campi.json",
    "armi_oggetti_militari": "rijksmuseum_armi_oggetti_militari_25_campi.json",
    "gioielli_accessori": "rijksmuseum_gioielli_accessori_25_campi.json",
    "modelli_manufatti_tecnici": "rijksmuseum_modelli_manufatti_tecnici_25_campi.json",
}

# Le prime 16 chiavi coincidono con lo schema dei dipinti omogenei.
# Le successive 9 conservano le informazioni aggiuntive introdotte nella normalizzazione.
FIELDS = (
    "object_uri", "inventory_numbers", "titles", "descriptions", "dimensions",
    "credit_line", "object_types", "support", "materials", "creators",
    "production_places", "current_locations", "production_dates", "visual_item_uris",
    "sets", "equivalent_uris",
    "alternative_titles", "object_description", "technical_description",
    "additional_dimensions", "inscriptions", "provenance", "related_object_notes",
    "production_techniques", "production_date_summary",
)

AAT = "http://vocab.getty.edu/aat/"
AAT_TECH = AAT + "300435429"
AAT_DIMS = AAT + "300435430"
AAT_CREDIT = AAT + "300026687"
AAT_SUBJECT = {AAT + "300435452", AAT + "300404670"}
AAT_INSCRIPTION = AAT + "300435414"
AAT_PROVENANCE = AAT + "300444174"
AAT_RELATED = AAT + "300435416"

DIM_RE = {name: re.compile(r"\b" + terms + r"\b", re.I) for name, terms in {
    "height": "(?:height|hoogte)",
    "width": "(?:width|breedte)",
    "depth": "(?:depth|diepte)",
    "thickness": "(?:thickness|dikte)",
    "length": "(?:length|lengte)",
    "diameter": "(?:diameter|doorsnede)",
    "weight": "(?:weight|gewicht)",
}.items()}

# Casi in cui ha senso parlare di un supporto (prevalentemente opere 2D).
# Per le sculture e le monete il materiale e' preservato in 'materials' e il
# supporto rimane vuoto, evitando ad esempio 'support: silver' su una moneta.
SUPPORT_CATEGORIES = {"stampe", "fotografie", "dipinti_e_pitture"}
SUPPORT_TERMS = {
    "canvas", "doek", "panel", "paneel", "paper", "papier (materiaal)",
    "parchment", "pergamena", "vellum", "cardboard", "carton", "karton",
    "copper", "copper (metal)", "koper", "ivory", "ivoor", "silk", "zijde",
    "linen", "linnen", "cloth", "textile", "wood (plant material)", "hout",
    "glass", "glas", "leather", "leer", "tin plate", "multiplex", "plywood"
}

# Non si riclassificano i concetti in ruoli in base alle etichette.
# I termini della colonna CSV `production_techniques` restano insieme
# in `production_techniques`, indipendentemente dal loro significato lessicale.
# Questo preserva l'attribuzione della colonna sorgente, senza pretendere
# che ogni termine denoti necessariamente un metodo di produzione.


def read_cell(raw, stats: Counter):
    """Converte solo la serializzazione JSON contenuta nelle celle del CSV."""
    if raw is None:
        return []
    raw = str(raw).strip()
    if not raw:
        return []
    if raw[0] in "[{":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            stats["celle_json_malformate"] += 1
            return []
    return raw


def as_list(value):
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def text_clean(v):
    if v is None:
        return ""
    value = html.unescape(str(v))
    # Note del catalogo possono contenere tag HTML per corsivi e paragrafi.
    value = re.sub(r"<\s*br\s*/?\s*>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


def unique(values):
    result, seen = [], set()
    for item in values:
        s = text_clean(item)
        if s and s not in seen:
            result.append(s)
            seen.add(s)
    return result


def preferred_values(items, stats: Counter, field: str):
    """Prima EN, altrimenti NL, infine qualsiasi lingua / senza indicazione."""
    items = [x for x in as_list(items) if isinstance(x, dict) and text_clean(x.get("value"))]
    for lng in ("en", "nl"):
        selected = [x.get("value") for x in items
                    if str(x.get("lang", "")).lower().split("-")[0] == lng]
        if selected:
            if lng == "nl":
                stats["fallback_olandese_" + field] += 1
            return unique(selected)
    return unique(x.get("value") for x in items)


def resource_names(resources, stats: Counter, field: str):
    out = []
    no_label = 0
    for resource in as_list(resources):
        if not isinstance(resource, dict):
            # Il CSV normale ha dizionari; non mostrare URL grezzi se non c'e' label.
            continue
        labs = preferred_values(resource.get("labels") or [], stats, field)
        if labs:
            out.extend(labs[:1])
        elif resource.get("uri"):
            no_label += 1
    if no_label:
        stats["risorse_senza_etichetta_" + field] += no_label
    return unique(out)


def note_values(descriptions, uris, stats: Counter, key: str):
    matches = []
    for note in as_list(descriptions):
        if isinstance(note, dict):
            kinds = note.get("description_type_uris") or []
            if isinstance(kinds, str):
                kinds = [kinds]
            if any(u in uris for u in kinds):
                matches.append(note)
    return preferred_values(matches, stats, key)


def dimensions_texts(descriptions, stats):
    items = note_values(descriptions, {AAT_DIMS}, stats, "dimensions")
    if not items:
        return "", []

    def rank(s):
        return (sum(bool(r.search(s)) for r in DIM_RE.values()),
                bool(re.search(r"\d", s)), len(s))

    best = max(items, key=rank)
    return best, [x for x in items if x != best]


def material_groups(materials, category, stats):
    vals = []
    for entry in as_list(materials):
        if isinstance(entry, dict):
            choices = preferred_values(entry.get("labels") or [], stats, "materials")
            if choices:
                vals.append(choices[0])
            elif entry.get("uri"):
                stats["risorse_senza_etichetta_materials"] += 1
    vals = unique(vals)
    if category not in SUPPORT_CATEGORIES:
        return "", "; ".join(vals)
    possible = [v for v in vals if v.casefold() in SUPPORT_TERMS]
    if len(possible) == 1:
        support = possible[0]
        remaining = [v for v in vals if v != support]
        return support, "; ".join(remaining)
    if len(possible) > 1:
        stats["supporti_ambigui"] += 1
    return "", "; ".join(vals)


def location_names(locations, stats):
    result = []
    for loc in as_list(locations):
        if isinstance(loc, str):
            result.append(loc)
        elif isinstance(loc, dict):
            names = preferred_values(loc.get("names_and_parts") or [], stats, "current_locations")
            identifiers = unique(x.get("value") for x in as_list(loc.get("identifiers_and_parts"))
                                 if isinstance(x, dict))
            full = next((x for x in identifiers if "-" in x), identifiers[0] if identifiers else "")
            parts = names + ([full] if full else [])
            if parts:
                result.append(" | ".join(parts))
    return unique(result)


def get_production_techniques(techniques, stats):
    """Mantiene tutte le etichette della colonna sorgente nell'ordine originario.

    Non riclassifica termini professionali come ruoli RDF.
    Conserva la precedente scelta di etichetta EN/NL e deduplicazione.
    """
    labels = []
    for resource in as_list(techniques):
        if not isinstance(resource, dict):
            continue
        text = resource_names([resource], stats, "production_techniques")
        if text:
            labels.append(text[0])
    return unique(labels)


def pretty_date(date_list):
    spans = []
    for event in as_list(date_list):
        if not isinstance(event, dict):
            continue
        raw_start = as_list(event.get("earliest_start"))
        raw_end = as_list(event.get("latest_end"))
        start = text_clean(raw_start[0]) if raw_start else ""
        end = text_clean(raw_end[-1]) if raw_end else ""
        # Anche gli anni a.C. usano date negative: conserviamo il segno e
        # non tentiamo conversioni arbitrarie in anni a.C. / a.E.V.
        y1 = re.match(r"(-?\d{1,6})-\d{2}-\d{2}", start)
        y2 = re.match(r"(-?\d{1,6})-\d{2}-\d{2}", end)
        a = y1.group(1) if y1 else ""
        b = y2.group(1) if y2 else ""
        if a and b:
            v = a if a == b else a + "–" + b
        else:
            v = a or b
        if v and v not in spans:
            spans.append(v)
    return "; ".join(spans)


def transform(raw, category, stats):
    obj = {key: read_cell(val, stats) for key, val in raw.items()}
    result = {}
    result["object_uri"] = text_clean(obj.get("object_uri"))
    inv = preferred_values(obj.get("inventory_numbers"), stats, "inventory_numbers")
    result["inventory_numbers"] = "; ".join(inv)
    titles = preferred_values(obj.get("titles"), stats, "titles")
    result["titles"] = titles[0] if titles else ""
    result["alternative_titles"] = titles[1:]

    descriptions = obj.get("descriptions")
    technical = note_values(descriptions, {AAT_TECH}, stats, "technical_description")
    subject = note_values(descriptions, AAT_SUBJECT, stats, "object_description")
    result["descriptions"] = "; ".join(technical or subject)
    result["object_description"] = "; ".join(subject)
    result["technical_description"] = "; ".join(technical)

    main_dim, other_dims = dimensions_texts(descriptions, stats)
    result["dimensions"] = main_dim
    result["additional_dimensions"] = other_dims
    result["credit_line"] = "; ".join(note_values(descriptions, {AAT_CREDIT}, stats, "credit_line"))
    result["inscriptions"] = note_values(descriptions, {AAT_INSCRIPTION}, stats, "inscriptions")
    result["provenance"] = note_values(descriptions, {AAT_PROVENANCE}, stats, "provenance")
    result["related_object_notes"] = note_values(descriptions, {AAT_RELATED}, stats, "related_object_notes")

    result["object_types"] = "; ".join(resource_names(obj.get("object_types"), stats, "object_types"))
    result["support"], result["materials"] = material_groups(obj.get("materials"), category, stats)
    result["creators"] = "; ".join(resource_names(obj.get("creators"), stats, "creators"))
    result["production_places"] = "; ".join(resource_names(obj.get("production_places"), stats, "production_places"))
    result["current_locations"] = location_names(obj.get("current_locations"), stats)
    result["production_dates"] = as_list(obj.get("production_dates"))
    result["production_date_summary"] = pretty_date(result["production_dates"])
    result["production_techniques"] = get_production_techniques(
        obj.get("production_techniques"), stats)

    result["visual_item_uris"] = "; ".join(unique(as_list(obj.get("visual_item_uris"))))
    result["sets"] = [{"uri": x} for x in unique(
        item.get("uri") for item in as_list(obj.get("sets")) if isinstance(item, dict))]
    result["equivalent_uris"] = unique(as_list(obj.get("equivalent_uris")))

    return {field: result[field] for field in FIELDS}


def load_mappings():
    if not MAPPING_FILE.is_file():
        raise FileNotFoundError(f"Mappatura mancante: {MAPPING_FILE}")
    payload = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    groups = payload.get("categories", {})
    mapping = {name: {entry["uri"].rstrip("/") for entry in groups[name]}
               for name in FILE_NAMES}
    generic = {entry["uri"].rstrip("/") for entry in payload.get("generic_vessels", [])}
    return mapping, generic


def get_object_uris(raw_cell, stats):
    val = read_cell(raw_cell, stats)
    result = set()
    for entry in as_list(val):
        if isinstance(entry, dict):
            u = entry.get("uri")
            if u:
                result.add(str(u).strip().rstrip("/"))
        elif isinstance(entry, str) and (entry.startswith("http://") or entry.startswith("https://")):
            result.add(entry.rstrip("/"))
    return result


# I nomi dei materiali sono gia' presenti nel CSV nelle etichette EN e NL.
# Solo se la classificazione e' un recipiente generico, li utilizziamo per
# evitare di attribuire un vaso di vetro ai manufatti ceramici, o viceversa.
CERAMIC_MAT = re.compile(
    r"\b(?:porcelain|porselein|ceramic|ceramics|keramiek|pottery|"
    r"earthenware|aardewerk|stoneware|steengoed|faience|faïence|"
    r"terracotta|terra cotta|majolica|maiolica|delftware|clay|"
    r"leem|loam|gres|grès)\b", re.I)
GLASS_MAT = re.compile(
    r"\b(?:glass|glas|glazen|crystal glass|lead glass|blown glass|"
    r"colourless glass|colorless glass)\b", re.I)


def material_signals(raw_cell, stats):
    materials = read_cell(raw_cell, stats)
    names = []
    for material in as_list(materials):
        if isinstance(material, dict):
            for label in as_list(material.get("labels")):
                if isinstance(label, dict) and label.get("value"):
                    names.append(text_clean(label["value"]))
    ceramic = any(CERAMIC_MAT.search(x) for x in names)
    glass = any(GLASS_MAT.search(x) for x in names)
    return ceramic, glass


def selected_macro(uris, mappings, generic, raw_materials, stats):
    matched = [name for name in PRIORITY if uris & mappings[name]]
    if uris & generic:
        ceramic, glass = material_signals(raw_materials, stats)
        if ceramic and glass:
            stats["recipienti_materiali_ceramica_e_vetro"] += 1
        elif ceramic:
            if "ceramiche_porcellane" not in matched:
                matched.append("ceramiche_porcellane")
            stats["recipienti_classificati_come_ceramica_da_materiali"] += 1
        elif glass:
            if "oggetti_vetro" not in matched:
                matched.append("oggetti_vetro")
            stats["recipienti_classificati_come_vetro_da_materiali"] += 1
        else:
            stats["recipienti_generici_senza_materiale_diagnostico"] += 1
    matched.sort(key=PRIORITY.index)
    return (matched[0] if matched else None), matched


def run(selected, argv=None):
    parser = argparse.ArgumentParser(
        description="Esporta dal CSV Rijksmuseum le categorie richieste con lo schema comune a 25 campi.")
    parser.add_argument("--input", type=Path, default=INPUT_CSV,
                        help="CSV completo, predefinito: ~/Desktop/rijksmuseum_completo.csv")
    parser.add_argument("--output-dir", type=Path, default=FOLDER,
                        help='Predefinito: ~/Desktop/macrocategorie json')
    parser.add_argument("--limit", type=int, default=0,
                        help="Massimo numero di oggetti per categoria; 0 = tutti")
    parser.add_argument("--max-rows", type=int, default=0,
                        help="Per prova: limita le righe analizzate del CSV; 0 = tutto")
    parser.add_argument("--overwrite", action="store_true",
                        help="Permette di sostituire soltanto i JSON e report di output, mai il CSV")
    args = parser.parse_args(argv)
    if args.limit < 0 or args.max_rows < 0:
        parser.error("--limit e --max-rows devono essere >= 0")
    selected = tuple(selected)
    for name in selected:
        if name not in FILE_NAMES:
            parser.error(f"Categoria sconosciuta: {name}")
    if len(selected) != len(set(selected)):
        parser.error("La stessa categoria e' stata richiesta piu' volte")
    src = args.input.expanduser().resolve()
    folder = args.output_dir.expanduser().resolve()
    if not src.is_file():
        parser.error(f"CSV originale non trovato: {src}")
    mapping, generic = load_mappings()
    folder.mkdir(parents=True, exist_ok=True)

    destinations = {name: folder / FILE_NAMES[name] for name in selected}
    reports = {name: folder / FILE_NAMES[name].replace(".json", "_report.json")
               for name in selected}
    outputs = [*destinations.values(), *reports.values()]
    if src in outputs:
        parser.error("L'input non puo' essere sovrascritto")
    if len(outputs) != len(set(outputs)):
        parser.error("Destinazioni di output duplicate")
    existing = [str(p) for p in outputs if p.exists()]
    if existing and not args.overwrite:
        parser.error("File di output gia' esistente (non sovrascritto):\n" + "\n".join(existing)
                     + "\nUsa --overwrite soltanto se desideri sostituirlo")

    counters = {cat: Counter() for cat in selected}
    present = {cat: Counter() for cat in selected}
    counts = Counter()
    shared_stats = Counter()
    rows_read = 0
    initial = {cat: True for cat in selected}
    temp_files = {cat: path.with_suffix(".json.part") for cat, path in destinations.items()}
    for path in temp_files.values():
        if path.exists():
            parser.error(f"File temporaneo gia' esistente: {path}")

    complete = False
    try:
        with ExitStack() as stack:
            outstreams = {}
            for name in selected:
                fh = stack.enter_context(temp_files[name].open("x", encoding="utf-8"))
                outstreams[name] = fh
                fh.write("[\n")
            src_fh = stack.enter_context(src.open("r", encoding="utf-8-sig", newline=""))
            csv.field_size_limit(sys.maxsize)
            reader = csv.DictReader(src_fh)
            required = {"object_uri", "object_types", "titles", "descriptions"}
            absent = required - set(reader.fieldnames or [])
            if absent:
                raise ValueError("Colonne assenti nel CSV: " + ", ".join(sorted(absent)))

            for row in reader:
                rows_read += 1
                types = get_object_uris(row.get("object_types"), shared_stats)
                macro, possible = selected_macro(types, mapping, generic, row.get("materials"), shared_stats)
                if not types:
                    shared_stats["oggetti_senza_tipologie_URI"] += 1
                if not macro:
                    shared_stats["oggetti_non_classificati_nelle_14_macrocategorie"] += 1
                if len(possible) > 1:
                    shared_stats["oggetti_con_macrogruppi_sovrapposti"] += 1
                    if macro in counters:
                        counters[macro]["assegnato_con_sovrapposizione"] += 1

                if macro in selected and (not args.limit or counts[macro] < args.limit):
                    stats = counters[macro]
                    norm = transform(row, macro, stats)
                    if not norm["object_uri"]:
                        stats["record_senza_URI_oggetto"] += 1
                        continue
                    if not initial[macro]:
                        outstreams[macro].write(",\n")
                    json.dump(norm, outstreams[macro], ensure_ascii=False, separators=(",", ":"))
                    initial[macro] = False
                    counts[macro] += 1
                    for key, value in norm.items():
                        if value:
                            present[macro][key] += 1

                if rows_read % 100_000 == 0:
                    print("Righe analizzate: {:,} | ".format(rows_read) + " | ".join(
                        f"{c}: {counts[c]:,}" for c in selected), flush=True)
                if args.max_rows and rows_read >= args.max_rows:
                    break
                if args.limit and all(counts[c] >= args.limit for c in selected):
                    break

            for name in selected:
                outstreams[name].write("\n]\n")
        # Gli output vengono resi definitivi soltanto dopo una scansione riuscita.
        for name in selected:
            os.replace(temp_files[name], destinations[name])
        complete = True
    finally:
        if not complete:
            for temp in temp_files.values():
                if temp.exists():
                    temp.unlink()

    for name in selected:
        report = {
            "macrocategoria": name,
            "file_input": str(src),
            "file_output": str(destinations[name]),
            "righe_csv_analizzate": rows_read,
            "oggetti_esportati": counts[name],
            "campi_per_oggetto": len(FIELDS),
            "elenco_campi": list(FIELDS),
            "campi_valorizzati": dict(present[name]),
            "avvertenze": dict(counters[name]),
            "diagnostica_classificazione": dict(shared_stats),
            "priorita_in_caso_di_sovrapposizione": list(PRIORITY),
            "tipologie_URI_prese_in_considerazione": len(mapping[name]) + (len(generic) if name in {"ceramiche_porcellane", "oggetti_vetro"} else 0),
            "limite_per_categoria": args.limit,
            "max_righe_prova": args.max_rows,
            "copertura": (
                "Ogni oggetto e' assegnato a una sola macrocategoria secondo una "
                "mappatura selettiva di URI del report delle tipologie; non e' "
                "la gerarchia ufficiale del museo. Le cinque categorie non "
                "coprono tutti gli oggetti del dataset. Le sovrapposizioni "
                "vengono risolte tramite priorita'."
            ),
            "lingua": "Inglese preferito; olandese solo in assenza di inglese nello stesso campo",
            "supporto": "Solo nelle tre categorie originali con oggetti 2D; negli altri casi i materiali restano nel campo materials",
            "recipienti": "Vasi, bicchieri, ciotole ecc. generici sono assegnati a ceramiche o vetro solo con materiali diagnostici",
            "date": "Date originali mantenute; riepilogo per intervallo di anni senza inferenze storiche",
            "origine_nuovi_campi": "Da titles, descriptions e production_techniques originali, senza interrogazioni esterne",
            "nota_production_techniques": "Contiene tutte le etichette della colonna CSV production_techniques senza suddivisione lessicale ROLE_NAMES; la struttura RDF va verificata per ciascuna fonte",
            "file_originale_invariato": True,
        }
        with reports[name].open("w", encoding="utf-8") as out:
            json.dump(report, out, indent=2, ensure_ascii=False)
            out.write("\n")
        print(f"{name}: {counts[name]:,} oggetti, 25 campi")
        print(f"  JSON: {destinations[name]}")
        print(f"  Report: {reports[name]}")
    print(f"Totale righe CSV analizzate: {rows_read:,}")
    if args.max_rows or args.limit:
        print("ATTENZIONE: esecuzione di prova o con limite; output non completo")
    return 0
