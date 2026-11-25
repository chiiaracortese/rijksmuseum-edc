# Mappatura semantica — procedura originale assistita da LLM

## Ruolo nella tesi

La mappatura documenta il significato dei **25 campi** dei JSON normalizzati e le corrispondenze concettuali con Linked Art e Getty AAT. Non converte i record in RDF, non riscrive i dataset e non costituisce un arricchimento delle opere. Questa cartella conserva il nome storico della mappatura; nella sequenza definitiva della tesi la mappatura è una **attività metodologica di supporto**, e l'arricchimento è la Fase 06.

**Metodo realmente seguito:** prompt assistito da LLM, analisi dello schema e del codice di normalizzazione, consultazione delle documentazioni di riferimento e verifica delle interpretazioni. Lo script `valida_mappatura.py` è un **controllo aggiuntivo successivo**, non lo strumento con cui è stata originariamente prodotta la mappatura.

## Materiali e procedura per ripetere il metodo

1. Procurarsi `schema_25_campi.json` (specifica tecnica, non dataset), lo script `macrocategorie_core_14.py`, e, se necessari, esempi o RDF acquisiti **separatamente**, nel rispetto delle rispettive condizioni d'uso.
2. Aprire una sessione LLM dotata dell'accesso ai materiali forniti e utilizzare **integralmente** il prompt approvato riportato sotto, allegando lo schema e il codice. Consultare la documentazione ufficiale Linked Art e Getty AAT per le corrispondenze.
3. Produrre la tabella ordinata di **25 righe e quattro colonne**: `campo_json`, `significato_locale`, `origine`, `corrispondenza_linked_art`.
4. Verificare manualmente le corrispondenze, distinguendo il modello Linked Art da percorsi RDF effettivamente osservati; poi applicare `valida_mappatura.py` come controllo strutturale supplementare.
5. Se si esporta un CSV, conservarlo **in locale**, senza aggiungerlo alla repository GitHub.

**Limiti di riproducibilità.** Lo stesso prompt può produrre formulazioni diverse con modelli/versioni diverse e richiede verifica umana. Il prompt originale riporta la dicitura storica «FASE 4»: viene conservata fedelmente, senza modificare la numerazione definitiva della tesi. Non sono documentati qui nome/versione del modello e parametri di inferenza originali: non vanno inventati.

## Prompt approvato integrale

Il testo seguente è riprodotto senza modifiche dal file approvato `prompt_semantic_mapping_estratto.txt`. Una copia in solo testo è disponibile come `PROMPT_APPROVATO.txt` per agevolare il copia-incolla.

```text
FASE 4 — Semantic Mapping assistito da LLM dei dati Rijksmuseum

Contesto

Stiamo sviluppando una pipeline per preparare i dati museali del Rijksmuseum alla pubblicazione e condivisione come data product JSON all'interno di un Data Space.

Le fasi 0–3 della pipeline sono concluse. Il dataset è stato normalizzato e organizzato in 14 macrocategorie, ciascuna contenente oggetti JSON descritti attraverso uno schema comune di 25 campi.

L'obiettivo della FASE 4 è produrre una mappatura semantica documentabile tra i 25 campi JSON e il modello Linked Art, affinché un futuro Consumer possa comprendere il significato delle informazioni, la loro origine e il rapporto concettuale con il modello semantico di riferimento.

Il risultato richiesto è una tabella di documentazione semantica del data product, non una conversione RDF o una ricostruzione del grafo originale.

1. Materiale di riferimento

Analizza congiuntamente i seguenti file:

schema_25_campi.json: definisce i 25 campi JSON, la loro struttura e i tipi di dato.

macrocategorie_core_14.py: documenta le operazioni effettivamente implementate durante la normalizzazione, incluse le trasformazioni locali, la selezione linguistica, i filtri AAT e le regole di estrazione.

Eventuali esempi JSON o triple RDF del Rijksmuseum: possono essere utilizzati esclusivamente per verificare informazioni effettivamente osservabili.

Utilizza come riferimento concettuale la documentazione ufficiale:

Linked Art: https://linked.art/

Getty AAT: https://www.getty.edu/research/tools/vocabularies/aat/

La documentazione Linked Art definisce le corrispondenze concettuali possibili, ma non dimostra automaticamente che un determinato percorso RDF sia presente nel dataset Rijksmuseum.

2. Obiettivo della mappatura

Per ciascuno dei 25 campi JSON devi identificare:

campo_json: il nome esatto del campo, senza modifiche.

significato_locale: il significato effettivo dell'informazione contenuta nel JSON dopo la normalizzazione.

origine: indicazione DIRETTA o DERIVATA, accompagnata da una descrizione sintetica dell'estrazione o trasformazione implementata.

corrispondenza_linked_art: la proprietà, classe o sequenza di proprietà Linked Art più appropriata e documentabile, con eventuali condizioni di validità.

La mappatura deve descrivere ciò che è effettivamente contenuto nei JSON normalizzati, senza attribuire loro informazioni o relazioni che non conservano.

3. Vincoli obbligatori

Non modificare i JSON, lo schema, gli script, i valori o le relazioni RDF originali.

Non creare nuove proprietà, classi, URI, ontologie o campi JSON.

Non introdurre corrispondenze semantiche prive di evidenze.

Non equiparare una corrispondenza concettuale Linked Art a un percorso RDF effettivamente osservato nel Rijksmuseum.

Non considerare le etichette testuali come se fossero gli URI originali delle risorse.

Non dedurre relazioni tra persone, attività produttive, tecniche o ruoli sulla base del solo significato lessicale delle etichette.

Non trasformare note descrittive in eventi, collegamenti tra oggetti o altre relazioni strutturate non documentate.

Non ricostruire informazioni eliminate, selezionate o aggregate durante la normalizzazione.

Quando il significato o la corrispondenza non sono completamente verificati, mantenere nella descrizione la relativa condizione, senza inventare una soluzione.

Non proporre ulteriori trasformazioni, modifiche alla pipeline o arricchimenti semantici.

4. Interpretazione dell'origine dei dati

Utilizza esclusivamente queste due categorie.

DIRETTA: informazione proveniente dalla corrispondente colonna del CSV, eventualmente sottoposta a operazioni tecniche di normalizzazione quali pulizia testuale, selezione linguistica, deduplicazione o aggregazione.

DERIVATA: informazione prodotta attraverso una selezione, separazione, composizione, filtro specifico o rielaborazione locale effettivamente implementata nello script.

La categoria DIRETTA non significa necessariamente che il valore sia identico alla serializzazione RDF originaria.

La categoria DERIVATA non implica un'inferenza semantica: può indicare una trasformazione locale deterministica.

5. Regole specifiche da rispettare

5.1 Selezione linguistica ed etichette

Lo script privilegia le etichette inglesi, in loro assenza quelle olandesi e infine altri valori disponibili.

Diversi campi JSON conservano etichette selezionate e aggregate, non gli URI originali dei concetti RDF.

Questo vale in particolare per:

object_types, materials, creators, production_places, production_techniques.

Anche inventory_numbers, titles, alternative_titles e current_locations sono soggetti a specifiche operazioni di selezione o composizione.

Le corrispondenze Linked Art devono quindi essere intese come riferimenti concettuali, senza presupporre che il Consumer possa ricostruire direttamente le risorse RDF originali.

5.2 Titoli

titles: contiene il primo titolo della selezione linguistica.

alternative_titles: contiene i titoli successivi al primo, ottenuti attraverso titles[1:].

Non considerare automaticamente titles un titolo principale dichiarato nella fonte RDF.

Non considerare automaticamente alternative_titles una classificazione di titoli alternativi già presente nel Rijksmuseum.

La corrispondenza Linked Art è identified_by → Name.content.

5.3 Descrizioni testuali

Lo script distingue diverse categorie di testi attraverso filtri Getty AAT.

technical_description

AAT 300435429: descrizione di materiali e tecniche.

Non interpretarlo come una generica descrizione tecnica.

Corrispondenza Linked Art: referred_to_by → LinguisticObject.content (Materials Statement).

object_description

AAT 300435452: physical description.

AAT 300404670: Primary Name.

I due concetti non sono semanticamente equivalenti.

Per le descrizioni fisiche utilizzare come riferimento referred_to_by → LinguisticObject.

Un'eventuale corrispondenza identified_by → Name è ammissibile soltanto quando confermata dalla fonte.

Mantenere esplicita l'incertezza relativa all'impiego di 300404670 nel filtro dello script.

descriptions

Lo script applica la priorità technical or subject.

Utilizza le descrizioni di materiali e tecniche quando disponibili; altrimenti quelle estratte come descrizioni dell'oggetto.

È una trasformazione locale.

Corrispondenza Linked Art: referred_to_by → LinguisticObject.content.

credit_line

Filtro AAT 300026687.

Corrispondenza: referred_to_by → LinguisticObject (Credit Line).

Non dedurre relazioni di proprietà, acquisizione o finanziamento.

inscriptions

Filtro AAT 300435414.

Corrispondenza: referred_to_by → LinguisticObject (Inscription Statement).

related_object_notes

AAT 300435416: descriptive note.

Il campo contiene note descrittive generali, eventualmente riferite ad altri oggetti.

Non attribuire automaticamente a tutti i contenuti relazioni con altri oggetti.

Corrispondenza: referred_to_by → LinguisticObject.content.

provenance

Lo script applica il filtro AAT 300444174.

Il significato di questo codice nel contesto del CSV non è ancora confermato.

Linked Art raccomanda AAT 300435438 per Provenance Statement.

Non considerare automaticamente equivalenti 300444174 e 300435438.

Corrispondenza prudente: referred_to_by → LinguisticObject.

La qualificazione come Provenance Statement resta subordinata alla verifica della fonte.

5.4 Dimensioni

dimensions deriva dal filtro AAT 300435430 e da un ranking lessicale che seleziona la descrizione principale.

additional_dimensions contiene le altre descrizioni dimensionali escluse dalla selezione principale.

Entrambi si riferiscono concettualmente a referred_to_by → LinguisticObject (Dimensions Statement).

Non interpretarli automaticamente come misure RDF strutturate, con valori numerici e unità di misura separati.

5.5 Materiali e supporti

materials contiene etichette selezionate dei materiali della fonte.

support deriva da un'euristica lessicale applicata soltanto a stampe, fotografie e dipinti_e_pitture.

Quando viene individuato un unico possibile supporto, questo viene separato dagli altri materiali.

Nelle altre macrocategorie i materiali restano nel campo materials.

La corrispondenza concettuale è made_of → Material.

Non attribuire automaticamente alla fonte Rijksmuseum un ruolo semantico esplicito di supporto: la distinzione introdotta dallo script è locale.

5.6 Produzione

creators

Contiene etichette testuali di creatori.

Possibile corrispondenza: produced_by → Production → carried_out_by → Actor.

Il collegamento deve essere verificato nella fonte RDF pertinente.

production_places

Contiene etichette dei luoghi associati alla produzione.

Possibile corrispondenza: produced_by → Production → took_place_at → Place.

Non attribuire automaticamente questo percorso a tutti gli oggetti.

production_techniques

Contiene le etichette selezionate dalla colonna CSV omonima.

Non viene effettuata una riclassificazione lessicale.

Possono comparire anche denominazioni professionali.

Nei campioni precedentemente verificati, painter e designer sono collegati attraverso il percorso produced_by → part → technique → Type.

Questa evidenza è limitata ai campioni esaminati.

Non trasformare automaticamente le etichette professionali in relazioni carried_out_by.

5.7 Date

production_dates

Conserva gli estremi cronologici presenti nei dati sorgente.

Non completa gli estremi mancanti.

Corrispondenza concettuale: produced_by → timespan → TimeSpan.

production_date_summary

È una trasformazione locale deterministica, non un'ipotesi.

È prodotta dalla funzione pretty_date(production_dates).

Estrae gli anni dagli estremi disponibili.

Conserva i segni negativi.

Deduplica i riepiloghi e unisce gli intervalli.

Non introduce inferenze cronologiche.

È concettualmente collegata a Production.timespan, senza costituire una nuova asserzione RDF autonoma.

5.8 Identificazione, localizzazioni e collegamenti

object_uri: HumanMadeObject.id.

inventory_numbers: identified_by → Identifier.content.

object_types: classified_as → Type.

current_locations: descrizioni composite prodotte localmente; possibile corrispondenza current_location → Place, da non generalizzare senza verifica.

visual_item_uris: URI dei contenuti visivi; corrispondenza shows → VisualItem. Non confondere VisualItem con un'immagine digitale.

sets: URI degli insiemi; possibile member_of → Set, subordinato alla natura delle risorse e del collegamento.

equivalent_uris: URI dichiarati equivalenti nella colonna sorgente; possibile equivalent, senza presupporre un'identità forte già verificata.

6. Campi da analizzare

Analizza esattamente questi 25 campi, mantenendo il seguente ordine:

object_uri

inventory_numbers

titles

descriptions

dimensions

credit_line

object_types

support

materials

creators

production_places

current_locations

production_dates

visual_item_uris

sets

equivalent_uris

alternative_titles

object_description

technical_description

additional_dimensions

inscriptions

provenance

related_object_notes

production_techniques

production_date_summary

7. Risultato richiesto

Produci direttamente un'unica tabella finale con esattamente 25 righe e le seguenti quattro colonne, nello stesso ordine:

Requisiti di compilazione:

campo_json: mantenere esattamente il nome originale.

significato_locale: descrivere sinteticamente il contenuto reale dopo la normalizzazione, includendo le precisazioni semantiche necessarie.

origine: utilizzare DIRETTA o DERIVATA, seguite dalla trasformazione effettivamente applicata nello script.

corrispondenza_linked_art: riportare la corrispondenza concettuale appropriata, indicando nella stessa cella eventuali condizioni o limiti già documentati.

Non aggiungere colonne relative a evidenze, decisioni umane, stati di verifica RDF o note per il Consumer.

Le incertezze indispensabili devono essere espresse direttamente nelle quattro colonne, senza introdurre informazioni aggiuntive.

Non produrre tabelle intermedie, nuove ipotesi di mappatura, classificazioni alternative o proposte di modifica ai dati.

Esportazione

Dopo aver prodotto la tabella, crea anche un file CSV scaricabile con:

Nome: semantic_mapping_rijksmuseum_25_campi_4_colonne.csv

Codifica: UTF-8

Intestazioni identiche alle quattro colonne richieste.

Esattamente 25 righe di dati.

Contenuti identici alla tabella mostrata, senza riassunti, abbreviazioni o variazioni.

Corretto trattamento di punti e virgola, virgolette, accenti, caratteri speciali e simboli delle proprietà Linked Art.

8. Controllo finale obbligatorio

Prima di presentare il risultato, verifica internamente che:

Tutti i 25 campi siano presenti una sola volta e nell'ordine stabilito.

Le trasformazioni DIRETTE e DERIVATE corrispondano al comportamento effettivo dello script.

production_date_summary sia riconosciuta come trasformazione deterministica.

I codici AAT siano interpretati secondo le correzioni indicate.

object_description non equipari physical description e Primary Name.

related_object_notes non implichi automaticamente relazioni fra oggetti.

provenance non equipari i codici AAT 300444174 e 300435438.

Le etichette testuali non siano confuse con gli URI RDF originali.

I percorsi painter e designer non siano generalizzati a tutto il dataset.

Non siano state introdotte corrispondenze o interpretazioni ulteriori rispetto a quelle documentate.

Output finale: esclusivamente la tabella consolidata a quattro colonne e il relativo file CSV, pronti per essere utilizzati come documentazione semantica del data product JSON destinato alla condivisione nel Data Space.

campo_json | significato_locale | origine | corrispondenza_linked_art
```
