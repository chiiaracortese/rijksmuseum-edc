"""Client HTTP locale per le quattro operazioni EDC studiate: scoperta, negoziazione, trasferimento."""
import json
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


class _SenzaRedirect(HTTPRedirectHandler):
    """Non seguire reindirizzamenti: la chiave Management non deve lasciare localhost."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


# Un unico punto mockabile nei test; nessuna rete viene usata senza comando esplicito.
def apri(richiesta, timeout):
    return build_opener(_SenzaRedirect()).open(richiesta, timeout=timeout)


def leggi_config_consumer(progetto: Path) -> dict:
    """Legge identità dichiarata e API key. ATTENZIONE: non verifica il processo Java attivo."""
    source = progetto / 'edc/consumer/config.properties'
    if source.is_symlink() or not source.is_file():
        raise ValueError('Configurazione Consumer assente o non sicura')
    options = {}
    for line in source.read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.strip().startswith('#'):
            continue
        name, _, value = line.partition('=')
        name = name.strip()
        if name in ('web.http.management.auth.key', 'edc.participant.id'):
            if name in options:
                raise ValueError('Chiave Consumer duplicata')
            options[name] = value.strip()
    if not options.get('web.http.management.auth.key') or not options.get('edc.participant.id'):
        raise ValueError('Chiave o identità del Consumer mancante')
    return {'chiave': options['web.http.management.auth.key'],
            'identita': options['edc.participant.id']}


def leggi_chiave_consumer(progetto: Path) -> str:
    return leggi_config_consumer(progetto)['chiave']


class ClientEDC:
    """Le sole risorse chiamabili sono endpoint EDC esplicitamente elencati."""
    def __init__(self, base: str, chiave: str):
        parsed = urlsplit(base)
        if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', 'consumer')
                or parsed.path.rstrip('/') != '/management/v4'
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.port is None):
            raise ValueError('L’API EDC deve essere localhost o host Docker consumer, /management/v4')
        if not chiave:
            raise ValueError('Chiave Management API mancante')
        self.base = base.rstrip('/')
        self.__chiave = chiave

    def _chiamata(self, metodo: str, percorso: str, payload=None) -> tuple[int, dict | list]:
        if percorso not in ('/catalog/request', '/contractnegotiations', '/transferprocesses'):
            kind, _, ident = percorso.lstrip('/').partition('/')
            if (metodo != 'GET' or kind not in ('contractnegotiations', 'transferprocesses')
                    or not ident or '/' in ident or not ident.replace('-', '').replace('_', '').replace('.', '').isalnum()):
                raise ValueError('Endpoint EDC non consentito')
        if metodo == 'POST' and percorso not in ('/catalog/request', '/contractnegotiations', '/transferprocesses'):
            raise ValueError('POST EDC non consentita')
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        req = Request(self.base + percorso, data=body,
                      headers={'X-Api-Key': self.__chiave, 'Content-Type': 'application/json',
                               'Accept': 'application/json'}, method=metodo)
        try:
            with apri(req, timeout=25) as reply:
                if reply.status not in (200, 201, 202):
                    raise RuntimeError(f'EDC ha restituito HTTP {reply.status}')
                content = reply.read()
                result = json.loads(content)
                if not isinstance(result, (dict, list)):
                    raise ValueError('Risposta EDC non valida')
                return reply.status, result
        except HTTPError as exc:
            raise RuntimeError(f'EDC: HTTP {exc.code} per {percorso.split("/")[1]}') from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError('EDC non raggiungibile o risposta non disponibile') from None

    def richiesta_catalogo(self, indirizzo_provider='http://provider:19194/protocol/2025-1') -> dict:
        payload = {'@context': {'@vocab': 'https://w3id.org/edc/v0.0.1/ns/'},
                   '@type': 'CatalogRequest', 'counterPartyId': 'provider',
                   'counterPartyAddress': indirizzo_provider,
                   'protocol': 'dataspace-protocol-http:2025-1'}
        _, result = self._chiamata('POST', '/catalog/request', payload)
        if not isinstance(result, dict):
            raise RuntimeError('Il catalogo non è un oggetto JSON')
        return result

    def invia_negoziazione(self, payload: dict) -> str:
        _, reply = self._chiamata('POST', '/contractnegotiations', payload)
        ident = reply.get('@id') if isinstance(reply, dict) else None
        if not isinstance(ident, str) or not ident:
            raise RuntimeError('ID negoziazione assente')
        return ident

    def leggi_negoziazione(self, ident: str) -> dict:
        _, obj = self._chiamata('GET', '/contractnegotiations/' + ident)
        if not isinstance(obj, dict):
            raise RuntimeError('Stato negoziazione non valido')
        return obj

    def invia_trasferimento(self, payload: dict) -> str:
        _, reply = self._chiamata('POST', '/transferprocesses', payload)
        ident = reply.get('@id') if isinstance(reply, dict) else None
        if not isinstance(ident, str) or not ident:
            raise RuntimeError('ID trasferimento assente')
        return ident

    def leggi_trasferimento(self, ident: str) -> dict:
        _, obj = self._chiamata('GET', '/transferprocesses/' + ident)
        if not isinstance(obj, dict):
            raise RuntimeError('Stato trasferimento non valido')
        return obj
