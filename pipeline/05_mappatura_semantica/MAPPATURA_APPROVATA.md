# Mappatura semantica approvata

Trascrizione della tabella definitiva di corrispondenza tra i 25 campi JSON e Linked Art.

La mappatura deriva dal procedimento assistito da LLM descritto nel README e nel prompt approvato.

| campo_json | significato_locale | origine | corrispondenza_linked_art |
| --- | --- | --- | --- |
| object_uri | URI identificativo dell’oggetto | DIRETTA: URI dal CSV, con pulizia testuale | HumanMadeObject.id |
| inventory_numbers | Numeri d’inventario selezionati e aggregati | DIRETTA: selezione linguistica, deduplicazione, concatenazione con ; | identified_by → Identifier.content |
| titles | Primo titolo della lingua selezionata | DIRETTA: preferenza EN, poi NL, poi altra lingua | identified_by → Name.content |
| descriptions | Descrizioni di materiali e tecniche; in assenza, descrizioni selezionate dell’oggetto | DERIVATA: priorità technical or subject, aggregazione testuale | referred_to_by → LinguisticObject.content |
| dimensions | Descrizione dimensionale selezionata come principale | DERIVATA: filtro AAT e ranking lessicale | referred_to_by → LinguisticObject (Dimensions Statement) |
| credit_line | Testo di riconoscimento o credito | DERIVATA: filtro AAT, selezione linguistica e aggregazione | referred_to_by → LinguisticObject (Credit Line) |
| object_types | Etichette delle tipologie dell’oggetto, non URI dei concetti | DIRETTA: estrazione etichette e aggregazione | classified_as → Type |
| support | Materiale identificato localmente come possibile supporto | DERIVATA: selezione lessicale da materials, solo per tre macrocategorie 2D | made_of → Material, senza ruolo di supporto dimostrato |
| materials | Etichette dei materiali, escluse quelle eventualmente trasferite in support | DERIVATA: selezione, separazione e aggregazione dei materiali | made_of → Material |
| creators | Etichette testuali dei creatori | DIRETTA: estrazione delle etichette, senza mantenere gli URI originali | produced_by → Production → carried_out_by → Actor |
| production_places | Etichette dei luoghi associati alla produzione | DIRETTA: selezione etichette e aggregazione | produced_by → Production → took_place_at → Place |
| current_locations | Descrizioni composite delle localizzazioni | DERIVATA: combinazione di nomi, parti e identificatori con  \|  | current_location → Place |
| production_dates | Estremi cronologici della produzione conservati dalla fonte | DIRETTA: struttura originale mantenuta, senza inferire estremi mancanti | produced_by → timespan → TimeSpan |
| visual_item_uris | URI dei contenuti visivi associati all’oggetto | DIRETTA: URI selezionati, deduplicati e concatenati | shows → VisualItem |
| sets | URI degli insiemi associati all’oggetto | DIRETTA: estrazione e deduplicazione degli URI | member_of → Set |
| equivalent_uris | URI di risorse dichiarate equivalenti nella colonna sorgente | DIRETTA: deduplicazione degli URI | equivalent |
| alternative_titles | Titoli successivi al primo nella selezione linguistica | DERIVATA: titles[1:] | identified_by → Name.content |
| object_description | Testi descrittivi relativi all’oggetto museale | DERIVATA: filtri AAT 300435452 e 300404670 | referred_to_by → LinguisticObject |
| technical_description | Descrizioni di materiali e tecniche | DERIVATA: filtro AAT e aggregazione testuale | referred_to_by → LinguisticObject.content (Materials Statement) |
| additional_dimensions | Ulteriori descrizioni dimensionali non selezionate come principali | DERIVATA: valori esclusi dal ranking della dimensione principale | referred_to_by → LinguisticObject (Dimensions Statement) |
| inscriptions | Testi descrittivi relativi alle iscrizioni | DERIVATA: filtro AAT e selezione linguistica | referred_to_by → LinguisticObject (Inscription Statement) |
| provenance | Testi estratti tramite AAT 300444174, senza significato di provenienza ancora confermato | DERIVATA: filtro AAT, selezione linguistica e deduplicazione | referred_to_by → LinguisticObject; Provenance Statement soltanto dopo verifica |
| related_object_notes | Note descrittive generali, eventualmente contenenti riferimenti ad altri oggetti | DERIVATA: filtro AAT, selezione e deduplicazione | referred_to_by → LinguisticObject.content |
| production_techniques | Termini associati alla realizzazione dell’oggetto, come paint, painter o designer. Possono indicare tecniche ma anche professioni. | DIRETTA: selezione linguistica e deduplicazione, senza riclassificazione lessicale | produced_by → part → technique → Type, dove verificato |
| production_date_summary | Sintesi leggibile degli anni di produzione | DERIVATA deterministica: pretty_date(production_dates) | Riferimento concettuale a Production.timespan, senza asserzione RDF autonoma |
