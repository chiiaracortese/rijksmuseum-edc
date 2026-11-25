# Riproducibilità delle attività assistite e delle regole d'uso

Questa repository separa **procedimento metodologico realmente usato**, **validazioni Python aggiunte per la distribuzione del codice** e **test sintetici**.

| Attività | Metodo originario | Materiale disponibile qui | Limite |
|---|---|---|---|
| Mappatura semantica (modulo storico 05) | Prompt LLM + revisione su schema e script + Linked Art/AAT | `05_mappatura_semantica/README.md`, prompt integrale, validatore | Non garantisce output testualmente identico |
| Arricchimento semantico (06) | Prompt LLM + ricerca delle fonti ufficiali + revisione | `06_arricchimento_semantico/README.md`, prompt integrale, validatore | Non sostituisce la ricerca verificabile e la revisione umana |
| Requisiti d'uso (08) | Decisione/approvazione umana dello Scenario A | `08_requisiti_uso/README.md`, specifica integrale, verificatore | Non è enforcement EDC |

I prompt approvati sono riprodotti integralmente, comprese le intestazioni storiche: **non** sono stati riformulati come se fossero script Python. I dataset museali, i CSV ottenuti dalle opere e i file JSON di arricchimento non vengono distribuiti. Gli input devono essere forniti separatamente; per il collaudo del codice sono disponibili test con dati sintetici.

Per una replica scientificamente tracciabile, annotare almeno: versione del codice, data/ora del test, modello LLM e versione se noti, eventuali parametri di generazione, prompt senza modifiche, input effettivo, URL e data di consultazione delle fonti, decisioni e stato della revisione umana. Se un elemento del lavoro storico non è stato registrato, dichiararlo **non documentato** anziché ipotizzarlo.
