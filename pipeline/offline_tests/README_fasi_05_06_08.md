# Moduli di verifica offline — supporto alle fasi 05, 06 e 08

Questi tre moduli **sono stati aggiunti per la riproducibilità della repository**, non
sono da descrivere retroattivamente come codice effettivamente eseguito durante
la realizzazione originale della tesi. Non alterano gli script delle fasi 01–04,
07, 09, il Control Plane, il Data Plane o il portale.

## Corrispondenza con il processo metodologico

- **05 – Mappatura semantica**: il pacchetto storico usa questa denominazione,
  ma la documentazione definitiva può trattarla come modulo di supporto alla
  fase semantica. `05_mappatura_semantica/valida_mappatura.py` **non inventa**
  alcuna corrispondenza: legge il CSV finale già approvato (fornito separatamente)
  e ne controlla intestazioni, 25 campi e ordine, significato e origine non vuoti,
  classificazione DIRETTA/DERIVATA con spiegazione. Non stabilisce correttezza
  ontologica né verifica che un percorso Linked Art sia presente nel Rijksmuseum.
- **06 – Arricchimento semantico assistito**:
  `06_arricchimento_semantico/valida_arricchimento.py` verifica una lista di
  arricchimenti **già prodotti e verificati documentalmente da una persona**,
  confrontandoli con gli identificativi e i titoli del JSON normalizzato; controlla
  limite di dieci, assenza di duplicati, otto campi obbligatori, URL sotto dominio
  ufficiale con HTTPS, lingua, evidenze e stato `pending_human_review`.
  Il codice non scarica fonti web, non esegue un LLM e **non può certificare**
  che una pagina sia stata davvero letta, che l'immagine corrisponda o che una
  descrizione non contenga elementi inventati. La revisione umana resta necessaria.
  Il JSON normalizzato originale non viene modificato.
- **08 – Requisiti d'uso**:
  `08_requisiti_uso/verifica_scenario_a.py` rappresenta le condizioni
  sperimentali **(R1 AND R2) OR R3**, incluse identità, emittente, validità,
  revoca e asset_scope. Carica le attestazioni esclusivamente da un registro di
  laboratorio **gestito dal Provider**. Non accetta attestazioni autoattribuite
  dal Consumer; non esegue crittografia, firma/VC, né negoziazione EDC. La
  Fase 09 rimane la generazione ODRL e la Fase 10 il motore applicativo reale.

Le condizioni sono **ipotetiche**, non licenze Rijksmuseum o vincoli sul pubblico dominio.
Il formato JSON del registro di test introdotto qui è una **interfaccia sintetica
per test** e non pretende di coincidere con `config/attestazioni.json` del progetto EDC.

## Esecuzione test senza dati originali

Dalla radice della repository, con Python 3.10+ (preferibilmente 3.11+):

```bash
python3 -m unittest discover -s pipeline/offline_tests -v
```

I nuovi test usano soltanto librerie standard. I test delle altre fasi
hanno dipendenze indicate nel `pipeline/offline_tests/requirements.txt`.

## Utilizzo su file esterni alla repository

```bash
python3 pipeline/05_mappatura_semantica/valida_mappatura.py \
  /percorso/esterno/semantic_mapping_rijksmuseum_25_campi_4_colonne.csv

python3 pipeline/06_arricchimento_semantico/valida_arricchimento.py \
  --normalized /percorso/esterno/dataset_25_campi.json \
  --enrichments /percorso/esterno/arricchimento_semantico.json

python3 pipeline/08_requisiti_uso/verifica_scenario_a.py \
  --request /percorso/esterno/request_sintetica.json \
  --provider-registry /percorso/esterno/registry_sintetico.json \
  --at 2026-11-20T12:00:00Z
```

Le cartelle indicate sono **esterne alla repository**. Non pubblicare dati o
attestazioni reali. Lo script 08 restituisce `0` se autorizza, `1` se nega e
`2` per input non valido; i due validatori restituiscono `0` per verifica
strutturale superata e `1` altrimenti.

### Struttura minima del registro sperimentale (solo test 08)

Il registry JSON locale prevede `trusted_issuers`, una mappa dei tre tipi di
attestazione a elenchi di emittenti riconosciuti, e `attestations`, un elenco
di record. Ogni record contiene `type`, `subject_id`, `issuer`, `valid_from`,
`valid_until` (timestamp ISO8601 con fuso), `revoked` (booleano) e `attributes`.
R1 controlla `organization_type`, `country_code`, `accreditation_status`.
R2 controlla `project_id`, `authorization_status`, `project_type` e `asset_scope`.
R3 controlla `organization_type`, `mandate_type`, `mandate_status` e `asset_scope`.
Per R2 `project_type` è uno fra `catalogazione`, `digitalizzazione`, `conservazione`.
Le richieste contengono soltanto `consumer_id` e `asset_id`; la verifica non
prende attestazioni dalla richiesta.

## Limiti rispetto alla tesi

L'archivio originale della Fase 05 documenta semantica locale, origini DIRETTE e
DERIVATE e corrispondenze Linked Art con caveat AAT. Per esempio:
- `production_date_summary` è un riepilogo deterministico, non inferenza RDF;
- `object_description` non equipara AAT 300435452 a 300404670;
- `provenance` non tratta AAT 300444174 e 300435438 come sinonimi;
- etichette testuali di `creators`, `production_places`, `production_techniques`
  non sono URI RDF ricostruiti.

Queste valutazioni semantiche **non vengono certificate dal programma**:
restano documentate nella tabella approvata da revisionare.

I test della Fase 06 non sono una replica delle visite alle pagine ufficiali né
delle descrizioni generate via LLM; il codice controlla solo la consistenza
formale e l'identità dei record.

La verifica di Fase 08 usa una trusted registry mock locale e non sostituisce i
112 test effettivi della politica e dei trasferimenti completati nella Fase 10.
