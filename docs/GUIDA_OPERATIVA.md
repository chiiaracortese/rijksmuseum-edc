# Guida operativa — Rijksmuseum Data Space (Provider e Consumer)

Questa guida accompagna il `README.md` principale e descrive **come utilizzare i sorgenti già presenti** nella repository. Non introduce un nuovo Data Space né sostituisce la metodologia della tesi.

> **Ambito:** installazione locale di ricerca. Le identità e le attestazioni sono sperimentali, non credenziali istituzionali reali. La discovery delle offerte non equivale all'autorizzazione all'accesso.

## 1. Prerequisiti e disponibilità dei dati

Sono necessari Docker con Compose, JDK 21, Python 3 e OpenSSL; Gradle scarica eventuali dipendenze mancanti. La repository distribuisce il codice, **non** i 14 dataset JSON Rijksmuseum, le immagini delle opere o le credenziali operative.

Per avviare la configurazione originale servono i 14 JSON nella cartella relativa `data/rijksmuseum/`, corrispondenti ai nomi, alle dimensioni e agli hash registrati in `config/edc-assets.json`. **Senza questi file, `python3 scripts/manage.py prepare` si interrompe correttamente:** non è possibile eseguire l'intero workflow originale con il solo codice GitHub.

**Vincolo del portale pubblicato:** `compose.yaml`, `ui_portale/server.py` e lo script macOS di avvio usano attualmente il nome di progetto `rijksmuseum-edc-interfaccia`. Per questa versione, il clone deve risiedere in una cartella con quel nome. Non utilizzare tale nome per una seconda istanza sullo stesso Docker host se esiste già un progetto omonimo: si rischia di intervenire sui suoi container. Non avviare più istanze senza prima isolare esplicitamente progetto Docker e porte.

Esempio su un computer che non possiede già un'installazione omonima:

```bash
git clone https://github.com/chiiaracortese/rijksmuseum-edc.git rijksmuseum-edc-interfaccia
cd rijksmuseum-edc-interfaccia
```

Dopo aver ottenuto *separatamente* i dataset previsti, collocarli in `data/rijksmuseum/` ed eseguire:

```bash
python3 scripts/manage.py prepare
python3 scripts/manage.py start
python3 scripts/manage.py bootstrap
python3 scripts/manage.py status
```

Il bootstrap registra/controlla il Data Plane, gli asset, le policy e le offerte; **non è una negoziazione**. In un'installazione già utilizzata, controllare preventivamente lo stato delle offerte ritirate prima di ripetere comandi di inizializzazione.

## 2. Identità sperimentali e condizioni d'uso

Il Provider valuta la condizione di accesso:

`(R1 AND R2) OR R3`

- **R1:** museo olandese con attestazione di accreditamento valida.
- **R2:** progetto culturale autorizzato, valido per l'identità Consumer e per il dataset richiesto (`asset_scope`).
- **R3:** autorità pubblica con mandato di tutela valido, anche in questo caso nell'ambito dell'asset richiesto.

Per provare le diverse situazioni, il registro `config/attestazioni.json` include identità **simulate**:

| Identità | Requisiti di prova | Esito previsto quando le attestazioni sono valide e lo scope include l'asset |
| --- | --- | --- |
| `museum_nl_01` | R1 + R2 | Accesso consentito |
| `museum_nl_02` | Solo R1 | Accesso negato |
| `heritage_authority_01` | R3 | Accesso consentito |
| `university_it_01` | Nessuno | Accesso negato |
| `test_r2_only_01` | Solo R2 | Accesso negato |

Il registro comprende altri profili combinati per i test. L'esito concreto viene deciso dal Provider **durante la negoziazione**, tenendo conto anche della validità, dell'emittente e dello `asset_scope` delle attestazioni. Un'identità autorizzata per un asset non è necessariamente autorizzata per gli altri.

### Cambiare identità Consumer da Terminale

Esempio:

```bash
python3 scripts/identita.py museum_nl_01
```

Lo script controlla che l'identità esista nel registro, aggiorna `edc/consumer/config.properties`, **ricrea il container Consumer** e riapplica la registrazione del Data Plane tramite bootstrap. Non modificare a mano soltanto il nome mostrato nell'interfaccia: l'identità dichiarata deve coincidere con quella del runtime attivo. Il cambio interrompe eventuali flussi in corso; eseguirlo soltanto tra due prove distinte.

## 3. Uso da Terminale: discovery, negoziazione e trasferimento

I comandi seguenti si eseguono dalla **radice del progetto** e usano il container `tools` della stessa installazione. Non richiedono di stampare o copiare le chiavi Management del Consumer.

**A. Visualizzare il catalogo EDC:**

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client catalogo
```

Per esaminare la presenza di una particolare offerta senza avviare la negoziazione:

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client offerta rijksmuseum-sculture-10-opere-unificate
```

La comparsa di un asset nel catalogo prova soltanto che l'offerta è stata pubblicata e scoperta. **Non prova che il Consumer possa accedervi.**

**B. Negoziare l'accesso con l'identità Consumer attiva:**

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client negozia rijksmuseum-sculture-10-opere-unificate --conferma
```

Leggere `STATO EDC`, `ESITO`, `AGREEMENT` ed `EVIDENZA`. L'esito positivo richiesto è `FINALIZED` / `AUTHORIZED`, con Agreement valido. Se compare `TERMINATED` o `DENIED_BY_POLICY`, **non avviare il trasferimento**: riesaminare i requisiti e l'ambito delle attestazioni. Conservare esattamente il percorso indicato dalla riga `EVIDENZA`.

**C. Trasferire solo con un accordo valido:**

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client trasferisci /project/evidence/workflow/negoziazioni/NOME_FILE_EVIDENZA.json --conferma
```

Sostituire `NOME_FILE_EVIDENZA.json` con **il nome effettivamente restituito** dalla negoziazione. Non creare percorsi arbitrari. Il comando produce un `TRANSFER PROCESS ID` e una nuova riga `EVIDENZA` relativa al trasferimento. Lo stato `STARTED` indica che il processo è stato avviato, **non** che il file è stato ricevuto.

**D. Verificare la ricezione e l'integrità:**

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client verifica /project/evidence/workflow/trasferimenti/NOME_FILE_TRANSFER.json
```

Usare il percorso esatto `EVIDENZA` restituito dal comando precedente. Il risultato richiesto è `TRANSFER_VERIFIED` con `6 / 6` controlli, inclusi accordo, asset, identificativi, dimensioni e SHA-256. Il file ricevuto si trova sotto `data/received/workflow/`; i report sotto `evidence/workflow/`. Non condividere tali file come parte del codice sorgente.

Per vedere tutti i comandi disponibili:

```bash
docker compose --profile tools run --rm --no-deps tools python -m edc_client --help
```

## 4. Uso tramite interfaccia web

Dopo avere avviato i quattro servizi EDC e completato il bootstrap, dalla radice del progetto, su un'installazione con il nome di cartella atteso:

```bash
python3 ui_portale/server.py
```

Aprire `http://127.0.0.1:45300` nel browser locale.

- Dalla schermata iniziale scegliere **Consumer**.
- Selezionare l'identità sperimentale e premere **Applica identità**. L'operazione aggiorna il runtime Consumer, non soltanto l'etichetta visualizzata.
- Premere **Interroga il catalogo EDC**, scegliere il dataset e consultare l'offerta e la descrizione delle condizioni d'accesso.
- Premere **Richiedi negoziazione contrattuale** e verificare lo stato dell'Agreement.
- Soltanto se autorizzati, premere **Richiedi trasferimento**, poi effettuare la **verifica** della ricezione; la galleria Consumer è disponibile soltanto dopo un trasferimento verificato.

La schermata **Provider** presenta lo stato degli asset, delle policy, delle offerte e dei processi. Comprende operazioni amministrative di revoca/ripubblicazione delle Contract Definition soggette ai controlli applicativi e alle conferme previste. La revoca impedisce nuove richieste basate sull'offerta ritirata; non cancella retroattivamente file già ricevuti o accordi precedentemente conclusi. Eseguire tali operazioni solo nell'ambiente locale controllato.

### Prima configurazione della password Provider

L'accesso amministrativo **Provider** richiede una password **locale**, definita dall'utente che installa il progetto. La password dell'autrice non è inclusa nella repository e non deve essere richiesta né condivisa. Il server legge il file `ui_portale/.provider-readonly-secret` e, su macOS/Linux, lo accetta soltanto se non è leggibile dagli altri utenti. Questo file è escluso da Git tramite `.gitignore`.

Dalla **radice del progetto**, eseguire una sola volta:

```bash
python3 - <<'PY'
from getpass import getpass
from pathlib import Path
import os

secret_file = Path('ui_portale/.provider-readonly-secret')
if secret_file.exists() or secret_file.is_symlink():
    raise SystemExit('Password Provider già configurata: nessuna modifica effettuata.')

password = getpass('Crea una password Provider (almeno 16 caratteri): ')
if len(password) < 16:
    raise SystemExit('La password deve contenere almeno 16 caratteri.')
if password != getpass('Conferma password: '):
    raise SystemExit('Le password non coincidono.')

old_umask = os.umask(0o077)
try:
    with secret_file.open('x', encoding='utf-8') as file:
        file.write(password + '\n')
    secret_file.chmod(0o600)
finally:
    os.umask(old_umask)

print('Password Provider configurata sul computer locale.')
PY
```

Il comando non mostra la password sullo schermo, non sovrascrive una configurazione esistente e non la carica su GitHub. All'avvio di `python3 ui_portale/server.py`, selezionare **Provider** e inserire la password scelta. Anche le operazioni amministrative di conferma possono richiederla nuovamente. Se la password viene persa, la sua sostituzione deve essere eseguita **localmente**, non modificando i file pubblicati; arrestare prima il portale e proteggere la nuova credenziale con gli stessi permessi. Questa autenticazione serve alla dimostrazione locale, **non** a esporre il portale su Internet.

Le fotografie e alcune risorse decorative non sono incluse nella distribuzione del codice; la galleria può mostrare segnaposto in assenza delle immagini.

## 5. Test, arresto e limiti di riproducibilità

Per eseguire i test del client e dell'architettura senza trasferimenti reali:

```bash
python3 -m unittest discover -s tests -v
```

Per interrompere l'infrastruttura gestita dallo script originale:

```bash
python3 scripts/manage.py stop
```

L'implementazione è **locale e dimostrativa**: l'autenticazione istituzionale è simulata, le condizioni di uso sono applicate in EDC tramite estensioni di policy personalizzate, e un unico Data Plane è condiviso. Non rappresenta un servizio di distribuzione pubblico pronto per Internet.

I test con dataset sintetici sono separati dai collaudi della tesi sui dataset originali. Il codice qui pubblicato consente di esaminare e ricompilare l'implementazione; per riprodurre esattamente i risultati originali sono necessari i dati e lo stato sperimentale pertinenti, distribuiti separatamente.

Per la descrizione dell'architettura e delle limitazioni consultare il [`README.md`](../README.md); per la pipeline metodologica vedere la cartella [`pipeline/`](../pipeline/).
