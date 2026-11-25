# Test offline con dati sintetici: fasi 01, 02, 03, 07 e 09

Questi test eseguono **i sorgenti originali** delle fasi 01, 02, 03, 07 e 09 su input fittizi creati durante l'esecuzione. Nessun dataset Rijksmuseum, fotografia, CSV reale, o attestazione è distribuito con la suite. Gli input e gli output temporanei vengono rimossi a fine test.

## Esecuzione

Dalla radice della repository, usando Python 3.10+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r pipeline/offline_tests/requirements.txt
python -m unittest discover -s pipeline/offline_tests -v
```

La suite verifica: generazione CSV da piccoli chunk N-Triples compressi (Fase 01); normalizzazione e classificazione in due macrocategorie con mappatura **fittizia** creata in una cartella temporanea (Fase 02); profiling descrittivo (Fase 03); produzione di schede per 14 arricchimenti fittizi e hash di un JSON sintetico (Fase 07); derivazione di offerte ODRL e bozze di contratti per 14 categorie e tabella di verità `(R1 AND R2) OR R3` (Fase 09).

**Cosa NON dimostra**: l'equivalenza ai risultati reali del Rijksmuseum, la validità scientifica della classificazione dei 14 dataset con la mappatura originale, i controlli della Fase 04 sui 951 record, la correttezza di un arricchimento LLM, l'esecuzione delle attestazioni R1/R2/R3 in Eclipse EDC, il trasferimento di asset e l'effettiva revoca/ripubblicazione. La Fase 09 genera *template di progetto*: gli ID di asset e la sintassi dei template vanno verificati e adattati alle configurazioni della Fase 10 in uso prima di qualsiasi deploy.

La suite crea le specifiche minime `input_fase8` solo per testare la generazione della Fase 09; **non** sostituisce la specifica approvata della Fase 08. I valori storici, i conteggi reali e le metriche della tesi non vengono simulati come risultati effettivi.

Si consiglia di eseguire separatamente anche la suite offline della Fase 04:

```sh
python -m pip install -r pipeline/04_validazione/requirements.txt
python -m unittest discover -s pipeline/04_validazione/offline_tests -v
```
