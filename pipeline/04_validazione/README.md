# Fase 04 — Validazione tecnica: test offline senza dataset

Questa directory comprende il codice operativo in `src/`, i test storici
in `tests/` e una suite separata in `offline_tests/`.

## Verifica senza i dati originali

La suite `offline_tests/test_synthetic.py` genera **esclusivamente in directory
temporanee** piccoli record fittizi, uno schema JSON Schema *minimo* e regole di
pre-check sperimentali. I JSON di prova non sono inclusi nella repository.

Dalla radice della repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r pipeline/04_validazione/requirements.txt
python -m unittest discover -s pipeline/04_validazione/offline_tests -v
```

L'esecuzione verifica il codice reale in `src/` per il percorso integrato:
profiling, convalida JSON Schema, pre-check di URI, unicità e date, generazione
dei report e verifica di non-modifica dell'input. Comprende dieci test.

**Limiti:** lo schema sintetico contiene soltanto i campi necessari ai test.
**Non** è lo schema Rijksmuseum definitivo a 25 campi. Un `OK` per questa
suite non dimostra la conformità dei dati originali, né replica il collaudo
storico sui 951 record, né autorizza la pubblicazione di dati.

## Test storici e configurazioni di produzione

I test in `tests/` sono stati conservati senza modifiche perché descrivono
verifiche storiche su materiale non distribuito nella repository. Per essere
eseguiti hanno bisogno anche di:

- `schemas/schema_25_campi.json` — schema di produzione;
- `config/prechecks_rijksmuseum.json` — regole di controllo;
- `input/rijksmuseum_strumenti_scientifici_musicali_25_campi.json` — **dataset
  originale escluso da GitHub**;
- `examples/esempio_valido.json` e `examples/esempio_con_errori.json` —
  esempi storici non inclusi.

Il test che controlla **951 record e SHA-256** è riproducibile soltanto usando
il file originale corrispondente. Non va convertito in un test sintetico
mantenendo le stesse aspettative.

Per la riproducibilità completa della validazione in produzione, lo schema e
la configurazione (che sono regole, non dataset) devono essere revisionati e
distribuiti separatamente dai dati, se privi di informazioni riservate.

## Dipendenze e attribuzione

Python >= 3.10, pacchetto `jsonschema` indicato in `requirements.txt`.
`src/validate_json.py` e `src/run_prechecks.py` dichiarano di essere derivati
in parte da componenti SPHN Connector coperti da **GNU GPL v3**. Prima di
pubblicare il repository al pubblico verificare e includere la licenza e le
attribuzioni richieste; gli script originali richiamano un file `LICENSE.txt`
che deve essere recuperato dal pacchetto di provenienza.

I test sintetici si limitano alla verifica del comportamento del software;
non sostituiscono le validazioni storico-scientifiche e le valutazioni dei
diritti.
