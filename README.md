# Rijksmuseum Data Space — Eclipse EDC

## Descrizione del progetto

**Rijksmuseum Data Space** è un'implementazione sperimentale di un Data Space locale basata su Eclipse EDC (*Eclipse Dataspace Components*), sviluppata nell'ambito di un progetto di tesi.

L'obiettivo è dimostrare la pubblicazione, la scoperta, la negoziazione contrattuale e il trasferimento controllato di dataset relativi al patrimonio culturale del Rijksmuseum.

Il progetto comprende:

- Un'infrastruttura Eclipse EDC con Provider e Consumer.
- Un Data Plane condiviso per il trasferimento dei dati.
- Un servizio locale di autenticazione OAuth2/JWT.
- Quattordici dataset JSON relativi a quattordici macrocategorie di opere.
- Una policy di accesso basata su requisiti istituzionali sperimentali.
- Un portale web con interfacce Provider e Consumer.
- Script Python per gestione, automazione, verifica e collaudo.

La repository è destinata alla condivisione dei **sorgenti software e della documentazione tecnica**. I dataset di grandi dimensioni sono distribuiti separatamente.

## 1. Architettura

L'infrastruttura comprende quattro servizi permanenti definiti in `compose.yaml`.

| Servizio | Funzione |
|---|---|
| `provider` | Control Plane che registra gli asset, pubblica le offerte e valuta le condizioni di accesso |
| `consumer` | Control Plane che esegue discovery, negoziazione e richieste di trasferimento |
| `data-plane` | Runtime Java condiviso che gestisce i flussi di dati tramite `HttpData-PULL` |
| `auth-service` | Servizio locale per l'autenticazione tecnica OAuth2/JWT e la pubblicazione JWKS |

Il container `tools` è utilizzato per operazioni temporanee di configurazione e collaudo.

I Control Plane interagiscono mediante i protocolli e le API supportati da Eclipse EDC. Il Data Plane realizza il trasferimento dei contenuti secondo il flusso configurato.

### Limiti sperimentali

Il Data Space è eseguito in un ambiente locale controllato.

L'utilizzo di un solo Data Plane condiviso costituisce una semplificazione architetturale e non rappresenta la separazione operativa fra organizzazioni indipendenti.

Le identità e le attestazioni istituzionali sono simulate per verificare le condizioni di autorizzazione. Il progetto non implementa una federazione reale di identità istituzionali verificabili.

## 2. Dataset e modello informativo

Il sistema è progettato per pubblicare **14 dataset JSON**, corrispondenti a 14 macrocategorie del patrimonio Rijksmuseum.

Ogni dataset contiene dieci schede di opere, per un totale di **140 opere**.

I file utilizzati dal Data Space sono collocati localmente in:

`data/rijksmuseum/`

I principali registri sono:

- `config/edc-assets.json`: identificativi, nomi dei file, dimensioni e hash SHA-256 attesi.
- `config/edc-assets.properties`: associazione tra Asset ID e sorgenti dei dati.
- `config/attestazioni.json`: registro sperimentale delle identità e delle attestazioni impiegate nelle verifiche di accesso.

I dataset JSON attualmente utilizzati per il trasferimento sono distinti dai dataset normalizzati a 25 campi delle fasi precedenti del lavoro. Secondo la documentazione tecnica del progetto, ogni scheda dei JSON pubblicati presenta 16 proprietà di primo livello.

### Disponibilità dei dati

**I 14 dataset JSON non sono inclusi nella repository GitHub.**

La loro distribuzione è prevista separatamente, attraverso una piattaforma dedicata ai dati di ricerca.

Prima di avviare un'installazione completa, i dataset devono essere collocati nella struttura prevista e verificati rispetto al registro `config/edc-assets.json`.

Il codice non deve sostituire i dataset mancanti con contenuti simulati.

La disponibilità pubblica e il collegamento permanente ai dataset saranno documentati quando verrà definita la relativa modalità di distribuzione.

## 3. Policy e controllo degli accessi

Il Provider applica una policy sperimentale basata su tre requisiti istituzionali.

- **R1 — Accreditamento museale:** il Consumer possiede un'attestazione valida come museo olandese accreditato.
- **R2 — Progetto culturale autorizzato:** il Consumer partecipa a un progetto culturale autorizzato e dispone di un'autorizzazione pertinente al dataset richiesto.
- **R3 — Mandato pubblico di tutela:** il Consumer è un'autorità pubblica con mandato valido per la tutela del patrimonio e con ambito di autorizzazione pertinente.

La regola di accesso è:

**(R1 AND R2) OR R3**

Le condizioni R2 e R3 prevedono anche un controllo dell'ambito autorizzato attraverso `asset_scope`.

Il sistema distingue la scoperta delle offerte dalla valutazione delle condizioni di accesso.

Un Consumer può individuare un'offerta nel catalogo senza essere necessariamente autorizzato a concludere la negoziazione o trasferire il dataset.

La valutazione della policy è effettuata dalle estensioni implementate nel Provider EDC.

## 4. Portale web

Il progetto include un portale web locale per l'interazione con il Data Space.

Il portale è organizzato in cinque schermate.

### 4.1 Home

Schermata iniziale per la selezione del ruolo:

- Provider.
- Consumer.

La scelta del ruolo determina il percorso dell'interfaccia, ma non sostituisce i controlli di autenticazione e autorizzazione.

### 4.2 Provider

L'interfaccia Provider permette di consultare le risorse pubblicate dal connettore.

Comprende:

- Stato del Provider.
- Dataset e asset registrati.
- Policy Definition e Contract Definition.
- Offerte pubblicate e relativa gestione.
- Negoziazioni contrattuali.
- Trasferimenti e relativi stati, quando disponibili.

Il progetto include funzionalità applicative per la gestione controllata delle offerte.

Le operazioni di amministrazione devono essere eseguite attraverso il backend locale e le API autorizzate, senza esporre al browser le chiavi Management del connettore.

### 4.3 Consumer

L'interfaccia Consumer permette di:

1. Selezionare un'identità sperimentale.
2. Eseguire la discovery del catalogo EDC.
3. Consultare dataset e offerte contrattuali.
4. Richiedere una negoziazione.
5. Verificare l'esito della negoziazione.
6. Richiedere il trasferimento quando autorizzato.
7. Controllare la ricezione e l'integrità del dataset.

Un esito positivo della negoziazione deve essere distinto dalla corretta conclusione del trasferimento.

### 4.4 Galleria

La galleria consente di esplorare le opere presenti nel dataset selezionato.

Sul lato Provider la consultazione utilizza i dati locali posseduti dal Provider.

Sul lato Consumer la consultazione dei dati trasferiti deve rispettare l'esito del workflow di autorizzazione e ricezione.

### 4.5 Scheda dell'opera

La scheda presenta le informazioni disponibili per una singola opera, utilizzando i dati del JSON selezionato.

Il portale riutilizza le risorse grafiche e i componenti di presentazione già sviluppati per la galleria.

### Sorgenti del portale

I principali sorgenti applicativi si trovano in:

`ui_portale/`

Fra questi:

- `server.py`
- `home.html`
- `provider.html`
- `provider.js`
- `provider_readonly.py`
- `provider_offers_admin.py`
- `index.html`
- `app.js`
- `portal.css`
- `portal-unified.css`
- `interfacce_2_3.py`

## 5. Requisiti software

Per ricostruire il sistema sono richiesti:

- Docker Desktop e Docker Compose.
- JDK 21.
- Python 3.
- OpenSSL.
- Accesso alle dipendenze Gradle, se non già presenti nella cache locale.

I componenti Java sono compilati utilizzando i Gradle Wrapper inclusi nel progetto.

## 6. Preparazione dell'ambiente

I comandi seguenti devono essere eseguiti dalla radice del progetto.

### 6.1 Recupero dei dataset

Prima della preparazione è necessario ottenere separatamente i 14 file JSON e collocarli nella directory:

`data/rijksmuseum/`

Il contenuto deve corrispondere a quanto dichiarato in `config/edc-assets.json`.

**Senza questi dati, la preparazione completa non può essere eseguita.**

### 6.2 Generazione delle configurazioni locali

Una volta disponibili i dataset:

```bash
python3 scripts/manage.py prepare
```

Il comando verifica la presenza e l'integrità dei file JSON e, quando necessario, genera le configurazioni tecniche locali.

Le credenziali operative non vengono distribuite tramite GitHub.

Le configurazioni del Provider e del Consumer possono essere generate a partire dai file `.example` previsti dal progetto.

### 6.3 Compilazione e avvio

```bash
python3 scripts/manage.py start
```

Il comando esegue le operazioni previste dallo script di gestione, inclusa la compilazione dei componenti Java e l'avvio dei servizi.

### 6.4 Registrazione delle risorse

Per l'inizializzazione prevista dall'implementazione:

```bash
python3 scripts/manage.py bootstrap
```

Il bootstrap registra o verifica le risorse del Data Space secondo il comportamento implementato nello script.

**Attenzione:** le operazioni di bootstrap non devono essere eseguite indiscriminatamente quando il Provider contiene già offerte modificate o ritirate.

Prima di ripetere il bootstrap in un ambiente già utilizzato, verificare il comportamento della versione corrente e le regole di conservazione dello stato di pubblicazione.

### 6.5 Stato dei servizi

```bash
python3 scripts/manage.py status
```

### 6.6 Arresto

```bash
python3 scripts/manage.py stop
```

## 7. Avvio del portale

Il portale utilizza il backend Python presente in `ui_portale/server.py`.

Nell'ambiente locale configurato, il portale è raggiungibile all'indirizzo:

`http://127.0.0.1:45300`

L'avvio del portale deve essere eseguito secondo la configurazione applicativa prevista, dopo aver predisposto i servizi necessari.

Le operazioni di amministrazione Provider sono destinate all'ambiente locale controllato e non devono essere esposte direttamente su Internet.

## 8. Test e verifiche

### Test Python offline

```bash
python3 -m unittest discover -s tests -v
```

I test offline permettono di verificare alcune funzionalità del codice senza eseguire trasferimenti reali.

### Discovery del catalogo

```bash
docker compose --profile tools run --rm --no-deps tools python scripts/collaudo.py --solo-catalogo
```

### Collaudo end-to-end

Esempio di verifica sul dataset Sculture:

```bash
docker compose --profile tools run --rm --no-deps tools python scripts/collaudo.py --asset rijksmuseum-sculture-10-opere-unificate --trasferisci
```

Il workflow comprende discovery, negoziazione, trasferimento quando autorizzato e controllo dell'integrità.

Lo stato `STARTED` di un Transfer Process non dimostra, da solo, che il file sia stato ricevuto correttamente.

### Selezione dell'identità Consumer

```bash
python3 scripts/identita.py museum_nl_01
```

Il comando seleziona un'identità già dichiarata nel registro sperimentale e aggiorna la configurazione del Consumer secondo il comportamento previsto dallo script.

Non crea una nuova identità istituzionale.

### Client EDC modulare

La directory `edc_client/` contiene un client Python per l'interazione con le API EDC.

La guida ai comandi può essere consultata nell'ambiente `tools` tramite:

```bash
python -m edc_client --help
```

## 9. Evidenze sperimentali

Durante i collaudi vengono prodotti dati, ricevute e report di verifica.

Le directory previste comprendono:

- `data/received/workflow/`: dataset ricevuti e ricevute di trasferimento.
- `evidence/`: report e risultati dei collaudi.

Queste directory contengono artefatti di esecuzione e non fanno parte della distribuzione ordinaria del codice.

I risultati dei collaudi descritti nella documentazione della tesi devono essere distinti dai test che un nuovo utilizzatore può riprodurre autonomamente.

## 10. Diagrammi e documentazione

La directory `docs/` contiene documentazione tecnica e rappresentazioni dell'architettura.

I file:

- `docs/componenti.png`
- `docs/componenti.svg`

contengono rappresentazioni grafiche delle componenti del sistema.

La documentazione tecnica deve essere interpretata in relazione alla versione del codice pubblicato.

## 11. Sicurezza e configurazioni locali

La repository non deve includere credenziali operative, chiavi private, token, dataset ricevuti o archivi locali delle offerte.

Sono esclusi, fra gli altri:

- `edc/auth-service/auth.env`
- `edc/auth-service/keys/`
- `edc/provider/config.properties`
- `edc/consumer/config.properties`
- `ui_portale/.provider-readonly-secret`
- `ui_portale/.provider-offer-archives/`
- `ui_portale/.portale-backups/`
- Directory di build e cache.

I file di configurazione locali devono essere generati per ciascuna installazione.

L'assenza dei file operativi esclusi dalla repository non autorizza a sostituirli con credenziali predefinite, chiavi pubblicate o dati simulati.

Le funzionalità di amministrazione non devono essere esposte senza adeguate misure di protezione.

## 12. Riproducibilità e limitazioni della distribuzione

Questa repository contiene i sorgenti e la documentazione del software, ma non costituisce da sola un ambiente immediatamente eseguibile.

Una riproduzione completa richiede:

1. Il recupero dei dataset originali nella versione attesa.
2. La verifica degli hash e della struttura dei dati.
3. La generazione delle credenziali locali.
4. La compilazione dei componenti EDC.
5. L'avvio e la configurazione dell'infrastruttura.
6. La registrazione delle risorse.
7. L'esecuzione delle verifiche funzionali.

I file di build, le cache, i dataset ricevuti e lo stato operativo locale sono esclusi dalla distribuzione.

Un'installazione nuova non eredita automaticamente lo stato delle offerte ritirate o i contratti negoziati nell'ambiente utilizzato durante la tesi.

## 13. Provenienza e diritti delle risorse grafiche

Il portale comprende fotografie di opere, un'illustrazione decorativa e diagrammi tecnici.

La provenienza di alcune risorse è descritta nel file:

`ui_portale/PROVENIENZA.txt`

La presenza di un'immagine nella distribuzione non implica automaticamente che tutte le sue condizioni di riutilizzo siano state verificate.

Prima di rendere pubblica la repository devono essere controllati i diritti di redistribuzione delle immagini e delle altre risorse di terze parti.

## 14. Distribuzione del codice e dei dati

Il codice sorgente viene distribuito attraverso GitHub.

I dataset di grandi dimensioni sono gestiti separatamente e saranno collegati alla documentazione quando sarà disponibile una modalità di distribuzione appropriata.

La scelta della licenza del software e le condizioni di redistribuzione delle risorse di terzi devono essere verificate prima della pubblicazione pubblica.

---

**Contesto:** progetto sperimentale di tesi relativo a interoperabilità, patrimonio culturale, Data Spaces ed Eclipse EDC.