"""Gestione autonoma dell'infrastruttura Rijksmuseum EDC essenziale.

Prepara credenziali e configurazioni locali, verifica i 14 dataset pubblicati,
compila i componenti Java e gestisce i servizi Docker.
"""

import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=ROOT):
    print('+', ' '.join(map(str, args)), flush=True)
    env = os.environ.copy()
    if args and args[0] == './gradlew':
        env['GRADLE_USER_HOME'] = str(ROOT / '.gradle-cache')
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def verify_datasets():
    """Verifica presenza, dimensione e SHA-256 dei 14 asset dichiarati."""
    registry_path = ROOT / 'config/edc-assets.json'
    assets = json.loads(registry_path.read_text(encoding='utf-8'))['assets']
    if len(assets) != 14:
        raise RuntimeError(f'Attesi 14 asset nel registro, trovati {len(assets)}')

    seen = set()
    for asset in assets:
        asset_id = asset['asset_id']
        filename = asset['filename']
        if asset_id in seen:
            raise RuntimeError(f'ID asset duplicato: {asset_id}')
        seen.add(asset_id)
        if Path(filename).name != filename or not filename.endswith('.json'):
            raise RuntimeError(f'Nome file non valido per asset {asset_id}')

        dataset = ROOT / 'data/rijksmuseum' / filename
        if not dataset.is_file() or dataset.is_symlink():
            raise RuntimeError(f'Dataset non trovato nel progetto: data/rijksmuseum/{filename}')

        digest = hashlib.sha256()
        size = 0
        with dataset.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(chunk)
                digest.update(chunk)

        if size != asset['size_bytes'] or digest.hexdigest() != asset['sha256']:
            raise RuntimeError(f'Dataset diverso dal registro (dimensione/SHA-256): {asset_id}')

    print(f'Integrità verificata: {len(assets)} dataset JSON.')


def prepare():
    # Il progetto usa solo dataset presenti nella propria cartella.
    verify_datasets()

    keys = ROOT / 'edc/auth-service/keys'
    keys.mkdir(parents=True, exist_ok=True)
    private, public = keys / 'jwt-private.pem', keys / 'jwt-public.pem'
    if private.exists() != public.exists():
        raise RuntimeError('Chiavi RSA incomplete: interrompo')
    if not private.exists():
        run('openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(private))
        run('openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public))
        private.chmod(0o600)

    envpath = ROOT / 'edc/auth-service/auth.env'
    if not envpath.exists():
        variables = [
            'PROVIDER_OAUTH_CLIENT_SECRET',
            'DATA_PLANE_OAUTH_CLIENT_SECRET',
            'CONSUMER_OAUTH_CLIENT_SECRET',
            'CONSUMER_DATA_PLANE_OAUTH_CLIENT_SECRET',
        ]
        envpath.write_text(
            ''.join(key + '=' + secrets.token_urlsafe(40) + '\n' for key in variables),
            encoding='utf-8',
        )
        envpath.chmod(0o600)

    for role in ('provider', 'consumer'):
        output = ROOT / f'edc/{role}/config.properties'
        if not output.exists():
            template = ROOT / f'edc/{role}/config.properties.example'
            output.write_text(
                template.read_text(encoding='utf-8').replace(
                    '__GENERATE_IN_SETUP__', secrets.token_urlsafe(32)
                ),
                encoding='utf-8',
            )
            output.chmod(0o600)

    (ROOT / 'data/received').mkdir(parents=True, exist_ok=True)
    print('Preparazione completata; credenziali non visualizzate.')


def main():
    command = sys.argv[1] if len(sys.argv) == 2 else None

    if command == 'prepare':
        prepare()
    elif command == 'start':
        prepare()
        control_plane = ROOT / 'edc/control-plane'
        data_plane = ROOT / 'edc/data-plane'
        run('./gradlew', ':provider:shadowJar', ':consumer:shadowJar', '--no-daemon', cwd=control_plane)
        run('./gradlew', 'installDist', '--no-daemon', cwd=data_plane)
        run('docker', 'compose', 'config', '--quiet')
        run('docker', 'compose', 'up', '-d')
        print('Avviati quattro container; bootstrap: python3 scripts/manage.py bootstrap')
    elif command == 'bootstrap':
        run('docker', 'compose', '--profile', 'tools', 'run', '--rm', '--no-deps',
            'tools', 'python', 'scripts/bootstrap.py')
    elif command == 'status':
        run('docker', 'compose', 'ps')
    elif command == 'stop':
        run('docker', 'compose', 'down')
    else:
        print('Uso: python3 scripts/manage.py prepare | start | bootstrap | status | stop')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        sys.exit('ERRORE: ' + str(exc))
