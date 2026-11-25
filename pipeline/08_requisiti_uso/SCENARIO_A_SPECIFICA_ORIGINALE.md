# Fase 8 — Derivazione requisiti d’uso

## Scenario A: cooperazione tra musei e autorità pubbliche

**Ambito:** requisiti ipotetici per controllare l’accesso al servizio sperimentale di scambio dati museali, non restrizioni giuridiche imposte dal Rijksmuseum. Le condizioni non modificano licenze o diritti dei dati originari.

**Risorsa:** i 14 dataset JSON normalizzati destinati a essere pubblicati dal Provider locale; primo test sul dataset *Dipinti e pitture*, successiva estensione alle altre 13 macrocategorie. I file di arricchimento LLM non rientrano automaticamente nel medesimo ambito e richiedono una decisione separata, tenendo conto dello stato di revisione.

**Regola:** `accesso = (R1 AND R2) OR R3`, subordinatamente alla corretta identificazione del richiedente e verifica delle prove.

## Requisiti

### R1 — Museo olandese accreditato

- Destinatario: organizzazione identificata come Consumer.
- Condizioni: `organization_type = museum`, `country_code = NL`, `accreditation_status = active`.
- Prova: attestazione istituzionale sperimentale `ExperimentalMuseumAccreditation`, proveniente da una fonte emittente considerata attendibile dal sistema sperimentale (numero e configurazione degli emittenti da decidere durante l’implementazione EDC).
- La prova deve essere riferita al Consumer autenticato e valida al momento della richiesta.
- Da solo R1 **non** basta per autorizzare l’accesso.

### R2 — Partecipazione a un progetto culturale autorizzato

- Destinatario: lo **stesso** Consumer cui si riferisce R1.
- Condizioni: progetto identificato da `project_id` non vuoto; autorizzazione `approved`; tipologia tra catalogazione, digitalizzazione, conservazione; asset richiesto incluso nella lista di quelli autorizzati; validità temporale attiva.
- Prova: attestazione sperimentale `ExperimentalCulturalProjectAuthorization` proveniente da una fonte emittente attendibile per le autorizzazioni progettuali.
- R2 deve essere congiunto a R1 per il percorso ordinario.

### R3 — Autorità pubblica con mandato di tutela

- Destinatario: organizzazione identificata come Consumer (può non essere un museo).
- Condizioni: `organization_type = public_authority`, `mandate_type = cultural_heritage_protection`, `mandate_status = active`; mandato applicabile all’asset e al Consumer richiedente; validità temporale.
- Prova: attestazione sperimentale `ExperimentalHeritageProtectionMandate` proveniente da una fonte emittente attendibile per i mandati di tutela.
- R3 costituisce un percorso **autonomo** rispetto a R1 e R2.

## Condizioni tecniche comuni (non sono un quarto requisito)

Per ciascuna prova necessaria al percorso autorizzativo considerato devono essere verificati: identità del soggetto corrispondente al Consumer, emittente riconosciuto dal sistema sperimentale, intervallo di validità, stato non revocato, integrità o attendibilità tramite il registro locale e ambito dell’asset quando previsto. Una prova mancante, non verificabile, scaduta o riferita a un soggetto differente non soddisfa il relativo requisito. In assenza di un percorso valido, negare l’accesso (*fail closed*). La non validità di una prova relativa a un percorso non deve impedire l’accesso quando l’altro percorso è completamente valido.

## Matrice decisionale

| R1 | R2 | R3 | Accesso |
|---|---|---|---|
| No | No | No | Negato |
| No | No | Sì | Consentito |
| No | Sì | No | Negato |
| No | Sì | Sì | Consentito |
| Sì | No | No | Negato |
| Sì | No | Sì | Consentito |
| Sì | Sì | No | Consentito |
| Sì | Sì | Sì | Consentito |

## Piano di realizzazione e verifica

**Fase 8:** definire e approvare questa specifica, il significato dei campi e gli esiti attesi. Non vengono create credenziali firmate né fissato il numero degli emittenti.

**Fase 9:** esprimere i requisiti in policy ODRL, stabilire scope e regole per il Policy Engine. ODRL non emette attestazioni.

**Implementazione EDC:** scegliere versione e IAM (mock controllato oppure VC), il numero e il ruolo degli emittenti; generare identità e attestazioni di laboratorio, mappare i claim, configurare le fonti di fiducia e implementare i controlli. Non bisogna permettere al Consumer di autoconferire arbitrariamente attributi attendibili.

**Test:** per ogni combinazione della tabella, verificare offerte/negoziazioni e, dove pertinente, il trasferimento. Aggiungere test negativi per scadenza, emittente non attendibile, identità non corrispondente e asset non autorizzato; testare inoltre il caso in cui un percorso sia valido e l’altro contenga una prova non valida. Nessun test EDC è stato ancora eseguito.

## Qualificazione giuridica e metodologica

Le regole sono condizioni ipotetiche per la distribuzione tramite il Provider sperimentale. Non sono licenze delle opere o vincoli sulle copie in pubblico dominio accessibili altrove. Un requisito di dichiarazione delle finalità non garantisce di per sé l’uso effettivo dei dati dopo il trasferimento.

## Riferimenti tecnici

- W3C ODRL Information Model: https://www.w3.org/TR/odrl-model/
- W3C Verifiable Credentials Data Model 2.0: https://www.w3.org/TR/vc-data-model/
- Eclipse EDC Samples policy enforcement: https://github.com/eclipse-edc/Samples/blob/main/policy/policy-01-policy-enforcement/README.md
- Rijksmuseum Information and Data Policy: https://data.rijksmuseum.nl/policy/
