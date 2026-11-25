#!/bin/bash
# Avvio del solo portale locale della copia indipendente.
# Non modifica o arresta alcun container Docker.
set -euo pipefail

cd "$(dirname "$0")"

if [ "$(basename "$PWD")" != "rijksmuseum-edc-interfaccia" ] || [ ! -f "compose.yaml" ]; then
  echo "ERRORE: questo avvio va collocato nella cartella rijksmuseum-edc-interfaccia."
  echo "Il progetto originale non deve essere utilizzato."
  read -r -p "Premi Invio per chiudere..." _ || true
  exit 1
fi

if [ ! -f "ui_portale/server.py" ]; then
  echo "ERRORE: non trovo ui_portale/server.py."
  echo "Verifica che la cartella ui_portale sia installata qui."
  read -r -p "Premi Invio per chiudere..." _ || true
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERRORE: python3 non e' disponibile nel Terminale."
  read -r -p "Premi Invio per chiudere..." _ || true
  exit 1
fi

URL="http://127.0.0.1:45300"
if /usr/bin/curl --silent --fail --max-time 2 "$URL/api/status" >/dev/null 2>&1; then
  echo "Il portale risulta gia' attivo. Apro il browser."
  /usr/bin/open -a "Google Chrome" "$URL" || /usr/bin/open "$URL"
  exit 0
fi

# Apre il browser appena il server locale risponde, senza un ritardo fisso.
(
  for ((i=0; i<60; i++)); do
    if /usr/bin/curl --silent --fail --max-time 1 "$URL/api/status" >/dev/null 2>&1; then
      /usr/bin/open -a "Google Chrome" "$URL" || /usr/bin/open "$URL"
      exit 0
    fi
    sleep 0.2
  done
  echo "Il portale non ha risposto. Controlla il messaggio d'errore del server nel Terminale."
) &

printf '\nRijksmuseum Data Space — Portale Discovery\n'
printf 'Cartella: %s\n' "$PWD"
printf 'URL: %s\n' "$URL"
printf 'Per chiudere il server, premi Ctrl+C in questa finestra.\n\n'
python3 -u ui_portale/server.py
