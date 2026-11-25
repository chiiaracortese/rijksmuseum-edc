"""Seleziona un'identità simulata già dichiarata nel registro delle attestazioni."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'edc/consumer/config.properties'


def main():
    if len(sys.argv) != 2:
        sys.exit('Uso: python3 scripts/identita.py <identità-del-registro>')

    identita = sys.argv[1]
    if identita not in json.loads((ROOT / 'config/attestazioni.json').read_text())['registry']:
        sys.exit('Identità non presente nel registro delle attestazioni simulate')

    if not CONFIG.is_file() or CONFIG.is_symlink():
        sys.exit('Configurazione Consumer assente: esegui prima python3 scripts/manage.py prepare')

    lines = CONFIG.read_text().splitlines(keepends=True)
    old = [i for i, line in enumerate(lines) if line.startswith('edc.participant.id=')]
    if len(old) != 1:
        sys.exit('edc.participant.id assente o duplicato; nessuna modifica effettuata')

    if lines[old[0]].strip() == 'edc.participant.id=' + identita:
        print('Identità già selezionata:', identita)
        return

    lines[old[0]] = 'edc.participant.id=' + identita + '\n'
    temp = CONFIG.with_suffix('.tmp')
    temp.write_text(''.join(lines))
    temp.chmod(0o600)
    os.replace(temp, CONFIG)

    print('Identità locale selezionata:', identita)
    print('Applico al solo Consumer di questo progetto...')
    subprocess.run(
        ['docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'consumer'],
        cwd=ROOT, check=True,
    )
    print('Riapplico la registrazione del Data Plane nel Control Plane Consumer...')
    subprocess.run(
        ['docker', 'compose', '--profile', 'tools', 'run', '--rm', '--no-deps',
         'tools', 'python', 'scripts/bootstrap.py'],
        cwd=ROOT, check=True,
    )
    print('Consumer aggiornato; la nuova identità può essere usata.')


if __name__ == '__main__':
    main()
