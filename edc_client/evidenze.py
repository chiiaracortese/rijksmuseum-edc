"""Scrittura e lettura delle evidenze della sola cartella Essenziale, senza sovrascritture silenziose."""
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')


def ora():
    return datetime.now(timezone.utc).isoformat()


def controlla_id(valore, cosa):
    if not isinstance(valore, str) or not ID.fullmatch(valore):
        raise ValueError(f'{cosa}: identificativo assente o non valido')
    return valore


def nuova(cartella: Path, nome: str, dati: dict) -> Path:
    cartella.mkdir(parents=True, exist_ok=True)
    percorso = cartella / nome
    with percorso.open('x', encoding='utf-8') as file:
        json.dump(dati, file, indent=2, ensure_ascii=False)
        file.write('\n')
    return percorso


def salva(percorso: Path, dati: dict):
    """Sostituzione atomica solo di una evidenza già riservata da Essenziale."""
    if not percorso.is_file() or percorso.is_symlink():
        raise RuntimeError('Evidenza non esistente o non sicura')
    temporaneo = percorso.with_name(percorso.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        with temporaneo.open('x', encoding='utf-8') as file:
            json.dump(dati, file, indent=2, ensure_ascii=False)
            file.write('\n')
        os.replace(temporaneo, percorso)
    finally:
        temporaneo.unlink(missing_ok=True)


def leggi(percorso: str | Path, cartella: Path) -> dict:
    source = Path(percorso)
    if source.is_symlink() or not source.is_file() or source.resolve().parent != cartella.resolve():
        raise ValueError('Evidenza esterna alla cartella prevista o non sicura')
    value = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Evidenza non valida')
    return value
