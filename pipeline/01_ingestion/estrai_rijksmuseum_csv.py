#!/usr/bin/env python3
"""Esporta i record RDF del toolkit Rijksmuseum in CSV, senza GraphDB.

Uso (prova sui 20 record forniti dal toolkit):
  python3 estrai_rijksmuseum_csv.py --dataset /percorso/sample_data/collection_20 \
      --output /percorso/fuori_dal_toolkit/anteprima20.csv

Uso (primo chunk, circa 1000 oggetti):
  python3 estrai_rijksmuseum_csv.py --dataset /percorso/rijksmuseum_data/collection \
      --output /percorso/fuori_dal_toolkit/prova1000.csv --max-files 1

Per elaborare tutti i chunk omettere --max-files, ma SOLO dopo aver verificato
un campione. I file .nt.gz e .json del toolkit sono letti e mai modificati.

Requisito: python3 -m pip install rdflib
"""
import argparse
import csv
import gzip
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    from rdflib import BNode, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, SKOS
    from rdflib.plugins.parsers.ntriples import W3CNTriplesParser
except ImportError:
    sys.exit("Manca rdflib. Installa la libreria con: python3 -m pip install rdflib")

CRM = "http://www.cidoc-crm.org/cidoc-crm/"
LA = "https://linked.art/ns/terms/"


def crm(name):
    return URIRef(CRM + name)


def la(name):
    return URIRef(LA + name)


P1 = crm("P1_is_identified_by")
P2 = crm("P2_has_type")
P4 = crm("P4_has_time-span")
P7 = crm("P7_took_place_at")
P9 = crm("P9_consists_of")
P14 = crm("P14_carried_out_by")
P32 = crm("P32_used_general_technique")
P43 = crm("P43_has_dimension")
P45 = crm("P45_consists_of")
P55 = crm("P55_has_current_location")
P106 = crm("P106_is_composed_of")
P65 = crm("P65_shows_visual_item")
P67 = crm("P67i_is_referred_to_by")
P90 = crm("P90_has_value")
P91 = crm("P91_has_unit")
P108I = crm("P108i_was_produced_by")
P190 = crm("P190_has_symbolic_content")
P72 = crm("P72_has_language")
P82A = crm("P82a_begin_of_the_begin")
P82B = crm("P82b_end_of_the_end")
P81A = crm("P81a_end_of_the_begin")
P81B = crm("P81b_begin_of_the_end")

# I termini RDF che servono alla selezione/interpretazione delle risorse.
KEPT = {
    RDF.type, RDFS.label, SKOS.prefLabel, SKOS.notation,
    P1, P2, P4, P7, P9, P14, P32, P43, P45, P55, P65, P67, P90, P91, P106,
    P108I, P190, P72, P82A, P82B, P81A, P81B,
    la("member_of"), la("equivalent"),
}

COLUMNS = [
    "object_uri", "inventory_numbers", "titles", "descriptions",
    "object_types", "materials", "dimensions", "creators",
    "production_places", "current_locations", "production_dates", "production_techniques",
    "visual_item_uris", "sets", "equivalent_uris",
]

# Lingue convenzionali del Rijksmuseum usate nella rappresentazione RDF.
LANG_URI = {
    "http://vocab.getty.edu/aat/300388277": "en",
    "http://vocab.getty.edu/aat/300388256": "nl",
}


class IndexSink:
    """Acquisisce solo le proprietà necessarie, senza creare un RDF store completo."""
    def __init__(self):
        self.by_subject = defaultdict(lambda: defaultdict(list))
        self.read_triples = 0
        self.kept_triples = 0

    def triple(self, subject, predicate, obj):
        self.read_triples += 1
        if predicate in KEPT:
            self.by_subject[subject][predicate].append(obj)
            self.kept_triples += 1


def read_chunk(path):
    sink = IndexSink()
    with gzip.open(path, "rb") as stream:
        W3CNTriplesParser(sink=sink).parse(stream)
    return sink


def values(index, subject, predicate):
    return index.get(subject, {}).get(predicate, ())


def unique(items):
    """Deduplica oggetti JSON senza perdere l'ordine dei valori distinti."""
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def json_cell(items):
    return json.dumps(unique(items), ensure_ascii=False, separators=(",", ":"))


def language(index, subject, lit=None):
    if isinstance(lit, Literal) and lit.language:
        return str(lit.language)
    for lang in values(index, subject, P72):
        code = LANG_URI.get(str(lang))
        if code:
            return code
    return ""


def symbolic(index, subject):
    return [
        {"value": str(obj), "lang": language(index, subject, obj)}
        for obj in values(index, subject, P190)
    ]


def labels(index, subject):
    out = []
    for pred in (SKOS.notation, SKOS.prefLabel, RDFS.label):
        out.extend(
            {"value": str(obj), "lang": language(index, subject, obj)}
            for obj in values(index, subject, pred)
        )
    if not out:
        out.extend(symbolic(index, subject))
    if not out:
        for name in values(index, subject, P1):
            if crm("E33_E41_Linguistic_Appellation") in values(index, name, RDF.type):
                out.extend(symbolic(index, name))
    return unique(out)


def ref(index, subject):
    """Mantiene sempre URI/label quando disponibili, non inventa etichette."""
    item = {"uri": str(subject)} if isinstance(subject, URIRef) else {}
    found = labels(index, subject)
    if found:
        item["labels"] = found
    return item


def resource_refs(index, subject, predicate):
    return [ref(index, obj) for obj in values(index, subject, predicate)
            if isinstance(obj, URIRef)]


def current_locations(index, subject):
    """P55 -> E53 Place (anche blank node) -> nomi spesso composti via P106.

    Non equivale necessariamente a una sede di esposizione attuale verificata
    in tempo reale: è la collocazione riportata nel record acquisito.
    """
    out = []
    for place in values(index, subject, P55):
        entry = ref(index, place)
        names, identifiers = [], []
        for name in values(index, place, P1):
            types = set(values(index, name, RDF.type))
            parts = []
            seen = set()
            stack = [name]
            while stack:
                part = stack.pop()
                if part in seen:
                    continue
                seen.add(part)
                parts.extend(symbolic(index, part))
                stack.extend(values(index, part, P106))
            if crm("E42_Identifier") in types:
                identifiers.extend(parts)
            else:
                names.extend(parts)
        if names:
            entry["names_and_parts"] = unique(names)
        if identifiers:
            entry["identifiers_and_parts"] = unique(identifiers)
        if isinstance(place, BNode):
            entry["node_kind"] = "blank_node"
        out.append(entry)
    return unique(out)


def main_names(index, subject):
    ids, names = [], []
    for node in values(index, subject, P1):
        types = set(values(index, node, RDF.type))
        entries = symbolic(index, node)
        for entry in entries:
            if crm("E42_Identifier") in types:
                ids.append(entry)
            elif crm("E33_E41_Linguistic_Appellation") in types:
                names.append(entry)
    return unique(ids), unique(names)


def descriptions(index, subject):
    out = []
    for node in values(index, subject, P67):
        for entry in symbolic(index, node):
            obj = dict(entry)
            # Per non perdere la natura documentaria delle descrizioni.
            types = [str(x) for x in values(index, node, P2) if isinstance(x, URIRef)]
            if types:
                obj["description_type_uris"] = sorted(set(types))
            out.append(obj)
    return unique(out)


def dimensions(index, subject):
    out = []
    for node in values(index, subject, P43):
        record = {
            "value": [str(x) for x in values(index, node, P90)],
            "types": resource_refs(index, node, P2),
            "units": resource_refs(index, node, P91),
        }
        # Non includere un blank-node ID instabile; deduplica per contenuto.
        if record["value"] or record["types"] or record["units"]:
            out.append(record)
    return unique(out)


def production(index, subject):
    actors, places, dates, techniques = [], [], [], []
    visited = set()
    pending = [(node, 0) for node in values(index, subject, P108I)]
    while pending:
        node, depth = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        actors.extend(resource_refs(index, node, P14))
        places.extend(resource_refs(index, node, P7))
        techniques.extend(resource_refs(index, node, P32))
        for span in values(index, node, P4):
            item = {}
            for pred, key in ((P82A, "earliest_start"), (P81A, "latest_start"),
                              (P81B, "earliest_end"), (P82B, "latest_end")):
                vals = [str(x) for x in values(index, span, pred)]
                if vals:
                    item[key] = vals
            if item:
                dates.append(item)
        if depth < 12:
            pending.extend((child, depth + 1) for child in values(index, node, P9))
    return unique(actors), unique(places), unique(dates), unique(techniques)


def extract_record(index, uri):
    subject = URIRef(uri)
    ids, names = main_names(index, subject)
    actors, places, dates, techniques = production(index, subject)
    return {
        "object_uri": uri,
        "inventory_numbers": json_cell(ids),
        "titles": json_cell(names),
        "descriptions": json_cell(descriptions(index, subject)),
        "object_types": json_cell(resource_refs(index, subject, P2)),
        "materials": json_cell(resource_refs(index, subject, P45)),
        "dimensions": json_cell(dimensions(index, subject)),
        "creators": json_cell(actors),
        "production_places": json_cell(places),
        "current_locations": json_cell(current_locations(index, subject)),
        "production_dates": json_cell(dates),
        "production_techniques": json_cell(techniques),
        "visual_item_uris": json_cell([str(x) for x in values(index, subject, P65)
                                      if isinstance(x, URIRef)]),
        "sets": json_cell(resource_refs(index, subject, la("member_of"))),
        "equivalent_uris": json_cell([str(x) for x in values(index, subject, la("equivalent"))
                                     if isinstance(x, URIRef)]),
    }


def accepted_objects(metadata_path):
    with metadata_path.open("r", encoding="utf-8") as stream:
        meta = json.load(stream)
    objects = [item[0] for item in meta["source_records"] if item[1] == "accepted"]
    if len(objects) != int(meta["accepted"]):
        raise ValueError("Metadati incoerenti in " + str(metadata_path))
    return objects


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Cartella contenente rdf/ e summary.json")
    parser.add_argument("--output", type=Path, required=True,
                        help="Percorso di un NUOVO CSV, esterno al toolkit")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Limita il test ai primi N file objects-*.nt.gz")
    parser.add_argument("--only-uri", default=None,
                        help="Facoltativo: estrai solo l'oggetto con questo URI")
    parser.add_argument("--resume", action="store_true",
                        help="Riprende un'estrazione interrotta dopo l'ultimo chunk completato")
    args = parser.parse_args()

    root, out = args.dataset.expanduser().resolve(), args.output.expanduser().resolve()
    folder = root / "rdf"
    if not folder.is_dir():
        parser.error("Cartella 'rdf' non trovata dentro --dataset: " + str(folder))
    if root == out or root in out.parents:
        parser.error("Per sicurezza, il file CSV deve essere salvato FUORI dalla cartella dei dati originali.")
    if out.exists():
        parser.error("Esiste già un file con questo nome: " + str(out))
    if args.max_files is not None and args.max_files < 1:
        parser.error("--max-files deve essere un intero positivo")

    files = sorted(folder.glob("objects-*.nt.gz"))
    if args.max_files is not None:
        files = files[:args.max_files]
    if not files:
        parser.error("Non sono stati trovati file objects-*.nt.gz")

    # Rifiuta un avvio lungo se non esiste il metadata di un chunk.
    for file in files:
        metadata = file.with_name(file.name.removesuffix(".nt.gz") + ".json")
        if not metadata.is_file():
            parser.error("Manca il file di metadati: " + str(metadata))

    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    progress = out.with_name(out.name + ".checkpoint.json")
    progress_tmp = progress.with_name(progress.name + ".tmp")

    if args.resume:
        if not (partial.is_file() and progress.is_file()):
            parser.error("Per --resume devono esistere il CSV .partial e il .checkpoint.json")
        state = json.loads(progress.read_text(encoding="utf-8"))
        expected = {"dataset": str(root), "output": str(out),
                    "file_count": len(files), "only_uri": args.only_uri,
                    "last_completed_file": files[state["completed_files"] - 1].name}
        for key, val in expected.items():
            if state.get(key) != val:
                parser.error("Checkpoint non compatibile ({}): {} != {}".format(key, state.get(key), val))
        next_file = int(state["completed_files"])
        total = int(state["rows_written"])
        selected = total
        found_target = bool(state.get("found_target", False))
        mode = "r+"
        print("Ripresa dal file {} di {}, righe già confermate: {}".format(next_file + 1, len(files), total))
    else:
        if partial.exists() or progress.exists():
            parser.error("Esistono file di un'esecuzione precedente. Usa --resume oppure rinominali/spostali prima di ricominciare.")
        next_file, total, selected, found_target = 0, 0, 0, False
        mode = "w"

    try:
        with partial.open(mode, newline="", encoding="utf-8-sig") as stream:
            if args.resume:
                stream.seek(int(state["position"]))
                stream.truncate()  # Scarta solo righe incomplete dopo l'ultimo checkpoint.
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            if not args.resume:
                writer.writeheader()

            for n in range(next_file, len(files)):
                file = files[n]
                metadata = file.with_name(file.name.removesuffix(".nt.gz") + ".json")
                objects = accepted_objects(metadata)
                if args.only_uri:
                    objects = [s for s in objects if s == args.only_uri]
                selected += len(objects)
                if objects:
                    print("[{} / {}] Lettura di {} ({} oggetti)".format(n + 1, len(files), file.name, len(objects)), flush=True)
                    sink = read_chunk(file)
                    for uri in objects:
                        writer.writerow(extract_record(sink.by_subject, uri))
                        total += 1
                    print("  Triple lette: {:,} | record CSV: {:,}".format(sink.read_triples, total), flush=True)
                if args.only_uri and objects:
                    found_target = True

                # Registra l'avanzamento SOLO dopo aver scritto interamente il chunk.
                stream.flush()
                os.fsync(stream.fileno())
                state = {"dataset": str(root), "output": str(out),
                         "file_count": len(files), "only_uri": args.only_uri,
                         "completed_files": n + 1, "last_completed_file": file.name,
                         "rows_written": total, "position": stream.tell(),
                         "found_target": found_target}
                progress_tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                progress_tmp.replace(progress)
                if args.only_uri and found_target:
                    break

        if args.only_uri and not found_target:
            raise ValueError("Oggetto non trovato nei metadati dei file selezionati: " + args.only_uri)
        if total != selected:
            raise ValueError("Conteggio non coerente: {} righe contro {} oggetti".format(total, selected))
        partial.replace(out)
        progress.unlink(missing_ok=True)
        print("\nCSV creato:", out)
        print("Righe di dati:", total)
        print("Nota: [] significa nessun valore recuperato in questo chunk, non un dato certamente inesistente.")
    except Exception:
        print("Esecuzione non completata. Nessun file originale modificato.", file=sys.stderr)
        print("Output parziale:", partial, file=sys.stderr)
        print("Dopo aver risolto l'errore, puoi riprendere aggiungendo --resume.", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
