#!/usr/bin/env python3
"""Portale locale Rijksmuseum: facciata per i comandi EDC esistenti nella SOLA copia.

Nessuna chiave EDC raggiunge il browser. Nessuna richiesta legge i dataset sorgente.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import time
import hmac
from http.cookies import SimpleCookie
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from interfacce_2_3 import IMAGE_DIR, CATEGORY_LABELS, render_gallery, render_opera_in_preparazione
from provider_readonly import snapshot as provider_snapshot, load_local_objects
from provider_offers_admin import (OfferError, list_offers, prepare as prepare_offer,
                                   commit as commit_offer)

APP = Path(__file__).resolve().parent
ROOT = APP.parent.resolve()
PROJECT = 'rijksmuseum-edc-interfaccia'
PORT_DEFAULT = 45300
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
OFFER_LOCK = threading.RLock()
PROVIDER_SESSIONS = {}
PROVIDER_SESSION_TTL = 1800

LABELS = {
    'armi-oggetti-militari': 'Armi e oggetti militari',
    'ceramiche-porcellane': 'Ceramiche e porcellane',
    'dipinti-e-pitture': 'Dipinti e pitture',
    'fotografie': 'Fotografie',
    'gioielli-accessori': 'Gioielli e accessori',
    'libri-documenti': 'Libri e documenti',
    'mobili-arredi': 'Mobili e arredi',
    'modelli-manufatti-tecnici': 'Modelli e manufatti tecnici',
    'monete-medaglie': 'Monete e medaglie',
    'oggetti-vetro': 'Oggetti in vetro',
    'sculture': 'Sculture',
    'stampe': 'Stampe',
    'strumenti-scientifici-musicali': 'Strumenti scientifici e musicali',
    'tessuti-abbigliamento': 'Tessuti e abbigliamento'
}
PROFILES = {
    # I nomi presentati all'utente sono descrittivi. Gli ID EDC non vengono modificati.
    'museum_nl_01': {
        'name': 'Museo olandese',
        'credentials': 'Museo accreditato con progetto culturale autorizzato',
        'group': 'Partecipanti principali'
    },
    'museum_nl_02': {
        'name': 'Museo senza autorizzazione al progetto culturale',
        'credentials': 'Museo accreditato, ma privo di un progetto culturale autorizzato',
        'group': 'Partecipanti principali'
    },
    'university_it_01': {
        'name': 'Altro ente (es. università)',
        'credentials': 'Ente senza attestazioni riconosciute per accedere ai dataset',
        'group': 'Partecipanti principali'
    },
    'heritage_authority_01': {
        'name': 'Autorità di tutela del patrimonio',
        'credentials': 'Autorità pubblica con mandato valido di tutela',
        'group': 'Partecipanti principali'
    },
    'test_r2_only_01': {
        'name': 'Partecipante a progetto senza accreditamento',
        'credentials': 'Progetto culturale autorizzato, senza accreditamento museale',
        'group': 'Altri profili di prova'
    },
    'test_r1_r3_01': {
        'name': 'Museo accreditato con mandato di tutela',
        'credentials': 'Accreditamento museale e mandato pubblico di tutela',
        'group': 'Altri profili di prova'
    },
    'test_r2_r3_01': {
        'name': 'Autorità di tutela con progetto culturale',
        'credentials': 'Progetto culturale autorizzato e mandato pubblico di tutela',
        'group': 'Altri profili di prova'
    },
    'test_r1_r2_r3_01': {
        'name': 'Museo con progetto autorizzato e mandato di tutela',
        'credentials': 'Accreditamento, progetto culturale autorizzato e mandato di tutela',
        'group': 'Altri profili di prova'
    }
}
assets = {a['asset_id']: a for a in json.loads((ROOT / 'config/edc-assets.json').read_text(encoding='utf-8'))['assets']}

def label(asset_id):
    short = asset_id.removeprefix('rijksmuseum-').removesuffix('-10-opere-unificate').removesuffix('-25-campi')
    return LABELS.get(short, short.replace('-', ' ').capitalize())

state = {'identity': None, 'catalog': None, 'offer': None, 'neg': None,
         'transfer': None, 'verified': None, 'objects': None, 'events': []}


def current_identity():
    file = ROOT / 'edc/consumer/config.properties'
    for line in file.read_text(encoding='utf-8').splitlines():
        if line.startswith('edc.participant.id='):
            return line.split('=', 1)[1].strip()
    raise RuntimeError('Identità non presente nella configurazione del Consumer')


def clear(after='identity'):
    keys = ['catalog', 'offer', 'neg', 'transfer', 'verified', 'objects']
    starts = {'identity': 0, 'catalog': 1, 'offer': 2, 'neg': 3, 'transfer': 4}
    for key in keys[starts[after]:]:
        state[key] = None


def log(message):
    state['events'].append(message)
    state['events'] = state['events'][-22:]


def command(args, timeout=210):
    cmd = list(args)
    try:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Operazione non conclusa entro il tempo di controllo; verificare i log prima di ripeterla') from exc
    except OSError as exc:
        raise RuntimeError('Impossibile avviare il comando locale') from exc
    output = (result.stdout or '') + '\n' + (result.stderr or '')
    if result.returncode != 0:
        detail = re.search(r'ERRORE:\s*([^\n]+)', output)
        msg = detail.group(1) if detail else 'Il comando EDC non è terminato correttamente'
        raise RuntimeError(msg[:700])
    return result.stdout


def cli(*args):
    return command(['docker', 'compose', '-p', PROJECT, '--profile', 'tools',
                    'run', '--rm', '--no-deps', 'tools', 'python', '-m', 'edc_client', *args])


def field(output, name):
    matched = re.search(r'^' + re.escape(name) + r':\s*(.*?)\s*$', output, re.M)
    if not matched:
        raise RuntimeError('Risposta EDC senza campo ' + name)
    return matched.group(1)


def evidence_from_output(output, section):
    raw = field(output, 'EVIDENZA')
    prefix = '/project/evidence/workflow/' + section + '/'
    if not raw.startswith(prefix) or '/' in raw[len(prefix):] or '\\' in raw:
        raise RuntimeError('Percorso di evidenza inatteso')
    real = (ROOT / raw.removeprefix('/project/')).resolve()
    directory = (ROOT / 'evidence/workflow' / section).resolve()
    if real.parent != directory or not real.is_file():
        raise RuntimeError('File di evidenza non trovato nella copia del progetto')
    return raw, json.loads(real.read_text(encoding='utf-8'))


def shape():
    actual = current_identity()
    if state['identity'] != actual:
        clear('identity')
        state['events'] = []
        state['identity'] = actual
    return {
        'identity': actual,
        'profiles': [{'id': k, **v} for k, v in PROFILES.items()],
        'catalog': state['catalog'], 'offer': state['offer'],
        'neg': state['neg'], 'transfer': state['transfer'],
        'verified': state['verified'], 'events': list(state['events'])
    }


def execute(action, body):
    shape()  # invalidare ogni esito di una vecchia identità, anche cambiata da Terminale
    if action == 'identity':
        ident = body.get('identity')
        registry = json.loads((ROOT / 'config/attestazioni.json').read_text(encoding='utf-8'))['registry']
        if ident not in PROFILES or ident not in registry:
            raise ValueError('Identità non disponibile nel registro della copia')
        if ident != state['identity']:
            command(['python3', 'scripts/identita.py', ident], timeout=180)
            if current_identity() != ident:
                raise RuntimeError('Consumer non aggiornato: verificare lo stato Docker')
        clear('identity')
        state['identity'] = ident
        state['events'] = []
        log('Identità Consumer applicata: ' + ident)
    elif action == 'discover':
        out = cli('catalogo')
        offered = []
        for match in re.finditer(r'^\s*-\s*(rijksmuseum-[\w-]+)\s*\|\s*OFFERTA\s*$', out, re.M):
            a = match.group(1)
            if a in assets and a not in offered:
                offered.append(a)
        if not offered:
            raise RuntimeError('Nessuna offerta EDC rilevata: la discovery non è riuscita')
        reported = int(field(out, 'Asset annunciati dal Provider'))
        if reported != len(offered):
            raise RuntimeError('Risposta del catalogo incoerente: numero di dataset non corrispondente')
        clear('identity')
        state['catalog'] = {'assets': [{'id': a, 'label': label(a)} for a in offered],
                            'datasets': reported,
                            'offers': int(field(out, 'Offerte per asset previsto'))}
        log('Discovery completata: ' + str(reported) + ' dataset; ' + str(state['catalog']['offers']) + ' offerte')
    elif action == 'offer':
        a = body.get('asset_id')
        discovered = {item['id'] for item in (state['catalog'] or {}).get('assets', [])}
        if a not in discovered:
            raise ValueError('Prima eseguire la discovery e selezionare un dataset realmente scoperto')
        out = cli('offerta', a)
        pos = out.find('{')
        if pos == -1:
            raise RuntimeError('Il Consumer non ha restituito i metadati dell’offerta')
        result, _ = json.JSONDecoder().raw_decode(out[pos:])
        if result['asset_id'] != a or result.get('numero_offerte', 0) < 1:
            raise RuntimeError('Offerta non disponibile nel catalogo')
        clear('catalog')
        state['offer'] = {'asset_id': a, 'label': label(a), 'filename': result.get('filename'),
                          'numero_offerte': result['numero_offerte'], 'offer_ids': result.get('offer_ids', [])}
        log('Offerta selezionata: ' + label(a))
    elif action == 'negotiate':
        offer = state['offer']
        if offer is None:
            raise ValueError('Selezionare prima un’offerta dal catalogo')
        if state['neg'] is not None:
            return shape()  # non duplicare negoziazioni al doppio click
        out = cli('negozia', offer['asset_id'], '--conferma')
        path, proof = evidence_from_output(out, 'negoziazioni')
        if proof.get('consumer_id_configurato') != state['identity'] or proof.get('asset_id') != offer['asset_id']:
            raise RuntimeError('Identità o dataset discordanti nell’evidenza di negoziazione')
        status = field(out, 'STATO EDC')
        outcome = field(out, 'ESITO')
        state['neg'] = {'state': status, 'outcome': outcome,
                        'negotiation_id': field(out, 'NEGOTIATION ID'),
                        'agreement_id': None if field(out, 'AGREEMENT') == 'ASSENTE' else field(out, 'AGREEMENT'),
                        'evidence': path}
        if status not in ('FINALIZED', 'TERMINATED'):
            raise RuntimeError('Negoziazione EDC senza stato conclusivo')
        log('Negoziazione ' + status + ': ' + outcome)
    elif action == 'transfer':
        neg = state['neg']
        if not neg or neg['state'] != 'FINALIZED' or neg['outcome'] != 'AUTHORIZED':
            raise ValueError('Trasferimento non consentito senza accordo autorizzato')
        if state['transfer'] is not None:
            return shape()  # trasferimento riservato a un singolo tentativo
        out = cli('trasferisci', neg['evidence'], '--conferma')
        path, proof = evidence_from_output(out, 'trasferimenti')
        if proof.get('consumer_id_configurato') != state['identity'] or proof.get('agreement_id') != neg['agreement_id']:
            raise RuntimeError('Identità o Agreement discordanti nel trasferimento')
        state['transfer'] = {'state': field(out, 'STATO EDC'),
                             'transfer_id': field(out, 'TRANSFER PROCESS ID'), 'evidence': path}
        log('Processo di trasferimento avviato: ' + state['transfer']['state'])
    elif action == 'verify':
        tr = state['transfer']
        if tr is None:
            raise ValueError('Nessun trasferimento da verificare')
        if state['verified'] is not None:
            return shape()
        out = cli('verifica', tr['evidence'])
        status = field(out, 'ESITO')
        checks = field(out, 'Sei controlli')
        if status != 'TRANSFER_VERIFIED' or not checks.startswith('6 / 6'):
            raise RuntimeError('Integrità del trasferimento non verificata')
        relative = Path(field(out, 'File ricevuto'))
        actual = (ROOT / relative).resolve()
        allowed = (ROOT / 'data/received/workflow').resolve()
        if allowed not in actual.parents or not actual.is_file() or actual.suffix != '.json':
            raise RuntimeError('JSON ricevuto non trovato nell’area autorizzata')
        objects = json.loads(actual.read_text(encoding='utf-8'))
        if not isinstance(objects, list):
            raise RuntimeError('Struttura del file ricevuto non compatibile con la galleria')
        state['verified'] = {'state': status, 'checks': checks,
                             'sha256': field(out, 'SHA-256'), 'file': str(relative)}
        state['objects'] = objects
        log('Integrità verificata: sei controlli superati. Galleria accessibile.')
    elif action == 'new':
        # Crea una nuova sessione VISIVA, non rimuove accordi o audit da EDC.
        clear('identity')
        log('Nuova richiesta: selezionare un dataset mediante discovery')
    else:
        raise ValueError('Operazione non supportata')
    return shape()


class Handler(BaseHTTPRequestHandler):
    server_version = 'RijksmuseumLocalPortal/1.0'

    def log_message(self, format, *args):
        return  # niente identificativi delle richieste nei log stdout

    def headers_common(self, content_type, length, cache='no-store'):
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

    def answer(self, code, data, content_type='application/json; charset=utf-8', extra_headers=None):
        payload = (json.dumps(data, ensure_ascii=False) if content_type.startswith('application/json') else data)
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        self.send_response(code)
        self.headers_common(content_type, len(payload))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def valid_host(self):
        # Riduce i rischi di DNS rebinding verso un servizio che opera su Docker.
        host = self.headers.get('Host', '').split(':')[0].strip().lower()
        return host in ('localhost', '127.0.0.1')

    def _static(self, path, mime):
        file = APP / path
        if not file.is_file() or file.is_symlink():
            return self.answer(404, {'error': 'File non trovato'})
        self.answer(200, file.read_bytes(), mime)

    def provider_authenticated(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            item = cookie.get('rijks_provider_session')
            token = item.value if item else ''
        except Exception:
            return False
        expiry = PROVIDER_SESSIONS.get(token) if token else None
        if not expiry or expiry < time.monotonic():
            return False
        return True

    def provider_session_key(self):
        if not self.provider_authenticated():
            return None
        try:
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            return cookie['rijks_provider_session'].value
        except (KeyError, ValueError):
            return None

    def provider_secret(self):
        path = APP / '.provider-readonly-secret'
        if not path.is_file() or path.is_symlink():
            return None
        # Su Unix/macOS richiede file non leggibile da altri utenti.
        if path.stat().st_mode & 0o077:
            return None
        return path.read_text(encoding='utf-8').strip()

    def provider_login(self, body):
        secret = self.provider_secret()
        password = body.get('password')
        if not secret or not isinstance(password, str) or not hmac.compare_digest(secret, password):
            return self.answer(403, {'error': 'Credenziale Provider non valida o non configurata'})
        token = secrets.token_urlsafe(32)
        PROVIDER_SESSIONS[token] = time.monotonic() + PROVIDER_SESSION_TTL
        return self.answer(200, {'authenticated': True}, extra_headers={
            'Set-Cookie': f'rijks_provider_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={PROVIDER_SESSION_TTL}'})

    def provider_logout(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            if 'rijks_provider_session' in cookie:
                PROVIDER_SESSIONS.pop(cookie['rijks_provider_session'].value, None)
        except Exception:
            pass
        return self.answer(200, {'authenticated': False}, extra_headers={
            'Set-Cookie': 'rijks_provider_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})

    def provider_gallery_route(self, route):
        if not self.provider_authenticated():
            return self.answer(403, 'Accesso Provider richiesto.', 'text/plain; charset=utf-8')
        match = re.fullmatch(r'/provider/(gallery|opera|image)/([a-z0-9-]+)(?:/(\d+))?', route)
        if not match:
            return self.answer(404, {'error': 'Risorsa non disponibile'})
        view, asset_id, index = match.groups()
        if asset_id not in assets or (view != 'gallery' and index is None) or (view == 'gallery' and index is not None):
            return self.answer(404, {'error': 'Asset o opera non presente nel registro'})
        try:
            objects = load_local_objects(ROOT, asset_id, assets[asset_id])
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.answer(404, {'error': str(exc)[:400]})
        CATEGORY_LABELS.setdefault(asset_id, label(asset_id))
        base = '/provider/gallery/' + asset_id
        if view == 'gallery':
            markup = render_gallery(objects, {'asset_id': asset_id})
            markup = markup.replace('href="/"', 'href="/provider"')
            markup = markup.replace('href="/opera/', 'href="/provider/opera/' + asset_id + '/')
            markup = markup.replace('src="/image/', 'src="/provider/image/' + asset_id + '/')
            return self.answer(200, markup, 'text/html; charset=utf-8')
        idx = int(index)
        if not 0 <= idx < len(objects):
            return self.answer(404, {'error': 'Indice opera non disponibile'})
        obj = objects[idx]
        if view == 'opera':
            markup = render_opera_in_preparazione(obj, idx)
            markup = markup.replace('href="/gallery"', 'href="' + base + '"')
            markup = markup.replace('src="/image/', 'src="/provider/image/' + asset_id + '/')
            return self.answer(200, markup, 'text/html; charset=utf-8')
        number = str(obj.get('inventory_numbers', ''))
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', number):
            return self.answer(404, {'error': 'Immagine non disponibile'})
        file = IMAGE_DIR / (number + '.jpg')
        if file.is_symlink() or not file.is_file() or not (20 < file.stat().st_size < 5_000_000):
            return self.answer(404, {'error': 'Immagine non disponibile'})
        return self.answer(200, file.read_bytes(), 'image/jpeg')

    def do_GET(self):
        if not self.valid_host():
            return self.answer(403, {'error': 'Host non autorizzato'})
        route = urlsplit(self.path).path
        if route == '/':
            return self._static('home.html', 'text/html; charset=utf-8')
        if route == '/consumer':
            return self._static('index.html', 'text/html; charset=utf-8')
        if route == '/provider':
            return self._static('provider.html', 'text/html; charset=utf-8')
        if route in ('/portal-unified.css', '/provider.js'):
            mime = 'text/css; charset=utf-8' if route.endswith('.css') else 'application/javascript; charset=utf-8'
            return self._static(route.lstrip('/'), mime)
        if route == '/api/provider/session':
            return self.answer(200, {'authenticated': self.provider_authenticated()})
        if route == '/api/provider/offers':
            if not self.provider_authenticated():
                return self.answer(403, {'error': 'Autenticazione Provider richiesta'})
            with OFFER_LOCK:
                return self.answer(200, list_offers(ROOT, assets, label))
        if route == '/api/provider/data':
            if not self.provider_authenticated():
                return self.answer(403, {'error': 'Autenticazione Provider richiesta'})
            return self.answer(200, provider_snapshot(ROOT, assets, label))
        if route.startswith('/provider/gallery/') or route.startswith('/provider/opera/') or route.startswith('/provider/image/'):
            return self.provider_gallery_route(route)
        if route == '/app.js':
            return self._static('app.js', 'application/javascript; charset=utf-8')
        if route == '/config.js':
            return self.answer(200, 'window.PORTAL_TOKEN=' + json.dumps(TOKEN) + ';', 'application/javascript; charset=utf-8')
        if route == '/portal.css':
            return self._static('portal.css', 'text/css; charset=utf-8')
        if route == '/style.css':
            return self._static('style.css', 'text/css; charset=utf-8')
        if route == '/hero-art.webp':
            return self._static('assets/hero-art.webp', 'image/webp')
        if route == '/api/status':
            with LOCK:
                return self.answer(200, shape())
        if route in ('/gallery', '/galleria'):
            with LOCK:
                shape()
                if not state['verified'] or not state['objects']:
                    return self.answer(403, 'Galleria disponibile solo dopo il trasferimento verificato.', 'text/plain; charset=utf-8')
                html = render_gallery(state['objects'], {'asset_id': state['offer']['asset_id']})
                # Torna al Consumer, non alla nuova Home, conservando la sessione visiva.
                html = html.replace('href="/"', 'href="/consumer"')
                return self.answer(200, html, 'text/html; charset=utf-8')
        if route.startswith('/opera/') or route.startswith('/image/'):
            is_img = route.startswith('/image/')
            try:
                index = int(route.rsplit('/', 1)[1])
            except ValueError:
                return self.answer(404, {'error': 'Opera sconosciuta'})
            with LOCK:
                shape()
                objs = state['objects'] if state['verified'] else None
                if not isinstance(objs, list) or not 0 <= index < len(objs):
                    return self.answer(403, {'error': 'Opera non disponibile senza accesso verificato'})
                if not is_img:
                    return self.answer(200, render_opera_in_preparazione(objs[index], index), 'text/html; charset=utf-8')
                number = str(objs[index].get('inventory_numbers', ''))
                if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', number):
                    return self.answer(404, {'error': 'Immagine non disponibile'})
                file = IMAGE_DIR / (number + '.jpg')
                if file.is_symlink() or not file.is_file() or not (20 < file.stat().st_size < 5_000_000):
                    return self.answer(404, {'error': 'Immagine non disponibile'})
                return self.answer(200, file.read_bytes(), 'image/jpeg')
        return self.answer(404, {'error': 'Pagina non trovata'})

    def do_POST(self):
        if not self.valid_host():
            return self.answer(403, {'error': 'Host non autorizzato'})
        origin = self.headers.get('Origin', '')
        if origin and origin not in (f'http://localhost:{self.server.server_port}', f'http://127.0.0.1:{self.server.server_port}'):
            return self.answer(403, {'error': 'Origine non autorizzata'})
        if self.headers.get('X-Portal-Token') != TOKEN:
            return self.answer(403, {'error': 'Richiesta non autorizzata'})
        if not self.headers.get('Content-Type', '').startswith('application/json'):
            return self.answer(415, {'error': 'Richiesta JSON richiesta'})
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 <= length <= 2048:
            return self.answer(413, {'error': 'Richiesta troppo lunga'})
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body, dict):
                raise ValueError('Corpo richiesta non valido')
            action = urlsplit(self.path).path.removeprefix('/api/')
            if action == 'provider/login':
                return self.provider_login(body)
            if action == 'provider/logout':
                return self.provider_logout()
            if action in ('provider/offers/prepare', 'provider/offers/commit'):
                session_id = self.provider_session_key()
                if not session_id:
                    return self.answer(403, {'error': 'Autenticazione Provider richiesta'})
                with OFFER_LOCK:
                    if action.endswith('/prepare'):
                        result = prepare_offer(ROOT, assets, session_id,
                                               body.get('asset_id'), body.get('operation'))
                    else:
                        password = body.get('password')
                        secret = self.provider_secret()
                        verified = isinstance(password, str) and bool(secret) and hmac.compare_digest(secret, password)
                        result = commit_offer(ROOT, assets, session_id,
                                              body.get('ticket'), verified, body.get('confirmation'))
                if (isinstance(result, dict) and result.get('ok')
                        and result.get('action') == 'revoke'):
                    # Solo sessione VISIVA del Consumer; nessun accordo, file o audit eliminato.
                    with LOCK:
                        if (state.get('offer') or {}).get('asset_id') == result.get('asset_id'):
                            clear('identity')
                            log('Offerta revocata: per una nuova richiesta occorre nuova discovery')
                return self.answer(200, result)
            if action.startswith('provider/'):
                return self.answer(405, {'error': 'Operazione Provider non permessa'})
            with LOCK:
                result = execute(action, body)
            return self.answer(200, result)
        except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
            return self.answer(400, {'error': str(exc)[:550]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=PORT_DEFAULT, type=int)
    args = parser.parse_args()
    if ROOT.name != PROJECT:
        raise SystemExit('STOP: installare SOLO in rijksmuseum-edc-interfaccia (mai nel progetto originale).')
    with LOCK:
        shape()
    httpd = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Portale Rijksmuseum pronto: http://127.0.0.1:{args.port}')
    print('Collegato esclusivamente alla copia:', ROOT)
    print('Per arrestare il portale: Ctrl+C')
    try:
        httpd.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        print('\nPortale arrestato.')
    finally:
        httpd.server_close()

if __name__ == '__main__':
    main()
