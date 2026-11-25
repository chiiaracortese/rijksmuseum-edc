# Estrazione delle 14 macrocategorie — schema a 25 campi

## Descrizione

Questa directory contiene gli script Python utilizzati per
estrarre dal CSV Rijksmuseum le opere appartenenti alle 14
macrocategorie previste dal progetto di tesi.

Gli output utilizzano uno schema comune a 25 campi.

## Sorgenti principali

- macrocategorie_core_14.py: logica condivisa di elaborazione.
- esegui_tutte_14_macrocategorie.py: esecuzione sulle 14 macrocategorie.
- estrai_*.py: script per le singole macrocategorie.
- esegui_nuove_nove_macrocategorie.py: esecuzione di un sottoinsieme.
- verifica_25_vs_26.py: script di verifica dello schema.

## Requisiti

Python 3.

Gli script analizzati utilizzano moduli della libreria
standard Python e il modulo locale macrocategorie_core_14.

## Dati di input

È necessario disporre del CSV Rijksmuseum completo,
generato durante la fase di acquisizione dei dati.

Il CSV non è incluso nella repository GitHub.

## Esempio di esecuzione

Dalla radice della repository:

python3 pipeline/02_normalizzazione/macrocategorie_25_campi/esegui_tutte_14_macrocategorie.py \
  --input data/rijksmuseum_completo.csv \
  --output-dir data/normalizzati_25_campi \
  --limit 10

## Parametri

--input       Percorso del CSV di origine.
--output-dir  Directory di destinazione.
--limit       Numero massimo di opere per categoria; 0 = tutte.
--max-rows    Numero massimo di righe CSV analizzate; 0 = tutte.
--overwrite   Consente di sostituire JSON e report esistenti,
              senza sovrascrivere il CSV originale.

## Note sulla riproducibilità

I percorsi predefiniti presenti negli script fanno riferimento
all'ambiente locale utilizzato durante lo sviluppo.

Per un'installazione esterna specificare esplicitamente
--input e --output-dir.

La validità sintattica e il funzionamento di --help sono stati
verificati. La riproduzione completa richiede il CSV di origine
e un ulteriore collaudo con dati effettivi.

I JSON normalizzati a 25 campi appartengono alla pipeline
di preparazione dei dati e devono essere distinti dai JSON
utilizzati nella successiva implementazione EDC.
