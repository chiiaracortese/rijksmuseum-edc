"""Render grafico delle interfacce 2 e 3 approvate nella demo del 18 novembre 2026.
Le funzioni HTML sono estratte SENZA MODIFICHE dal file attivo scripts/demo_museale.py.
Questo modulo non avvia EDC, non negozia, non cambia identità.
Chiamarlo soltanto con oggetti JSON GIA' ricevuti e verificati da EDC.
"""
from __future__ import annotations
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / "demo-ui" / "images"
ASSET_ID = "rijksmuseum-dipinti-e-pitture-10-opere-unificate"
CATEGORY_LABELS = {
    "rijksmuseum-armi-oggetti-militari-10-opere-unificate": "Armi e oggetti militari",
    "rijksmuseum-ceramiche-porcellane-10-opere-unificate": "Ceramiche e porcellane",
    "rijksmuseum-dipinti-e-pitture-10-opere-unificate": "Dipinti e pitture",
    "rijksmuseum-fotografie-10-opere-unificate": "Fotografie",
    "rijksmuseum-gioielli-accessori-10-opere-unificate": "Gioielli e accessori",
    "rijksmuseum-libri-documenti-10-opere-unificate": "Libri e documenti",
    "rijksmuseum-mobili-arredi-10-opere-unificate": "Mobili e arredi",
    "rijksmuseum-modelli-manufatti-tecnici-10-opere-unificate": "Modelli e manufatti tecnici",
    "rijksmuseum-monete-medaglie-10-opere-unificate": "Monete e medaglie",
    "rijksmuseum-oggetti-vetro-10-opere-unificate": "Oggetti in vetro",
    "rijksmuseum-sculture-10-opere-unificate": "Sculture",
    "rijksmuseum-stampe-10-opere-unificate": "Stampe",
    "rijksmuseum-strumenti-scientifici-musicali-10-opere-unificate": "Strumenti scientifici e musicali",
    "rijksmuseum-tessuti-abbigliamento-10-opere-unificate": "Tessuti e abbigliamento",
}

def safe(value):
    return html.escape(str(value), quote=True)

def autore_opera(inventory_number):
    # Fonte ausiliaria: metadati Rijksmuseum; MAI il dataset non trasferito.
    try:
        records = json.loads((ROOT / 'demo-ui/autori_dipinti.json').read_text(encoding='utf-8'))
        item = records.get('opere', {}).get(inventory_number, {})
        return item.get('autore') or 'Autore non indicato'
    except (OSError, ValueError, TypeError):
        return 'Autore non indicato'

def render_gallery(objects, result):
    # Seconda schermata: solo opere del JSON ricevuto e verificato.
    tiles = []
    label = CATEGORY_LABELS[result['asset_id']]
    for index, obj in enumerate(objects):
        number = str(obj.get('inventory_numbers', ''))
        title = str(obj.get('titles', 'Senza titolo'))
        authors = render_lines(obj.get('creators'))
        author = ' · '.join(authors) if authors else (autore_opera(number) if result['asset_id'] == ASSET_ID else 'Autore non indicato')
        image_path = IMAGE_DIR / (number + '.jpg')
        if image_path.is_file() and not image_path.is_symlink() and 20 < image_path.stat().st_size <= 5_000_000:
            image = f'<img src="/image/{index}" alt="{safe(title)}" loading="lazy" decoding="async">'
        else:
            image = '<div class="collection-no-image"><span class="collection-sigil" aria-hidden="true">✦</span><span>Immagine non disponibile</span></div>'
        tiles.append(f'''<a class="collection-tile collection-tile-{(index % 6) + 1}" href="/opera/{index}" data-inventory="{safe(number)}" aria-label="Apri {safe(title)} di {safe(author)}">
          <div class="collection-frame">{image}<span class="collection-visit" aria-hidden="true">↗</span></div>
          <div class="collection-name">{safe(title)}</div>
          <div class="collection-author">{safe(author)}</div>
        </a>''')
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe(label)} · Rijksmuseum Data Space</title><link rel="stylesheet" href="/style.css"></head>
    <body class="collection-page"><header class="collection-header">
      <a class="collection-brand" href="/" aria-label="Torna alla pagina iniziale">R<span>·</span> Rijksmuseum <small>DATA SPACE</small></a>
      <a class="collection-home" href="/">← Torna all'accesso</a>
    </header><main class="collection-main">
      <div class="collection-head"><div><span class="collection-eyebrow">COLLEZIONE</span><h1>{safe(label)}</h1>
      <p>Dieci opere da esplorare. Seleziona un'immagine per aprire la scheda dell'opera.</p></div>
    </div>
      <section class="collection-masonry" aria-label="Galleria di dieci opere">{''.join(tiles)}</section>
    </main><footer class="collection-footer"><span>Progetto di tesi indipendente, non affiliato al Rijksmuseum.</span><span>Immagini: Rijksmuseum, Amsterdam, dove disponibili.</span></footer>
    </body></html>'''

def flatten_field(value):
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(flatten_field(item))
        return [p for p in parts if p]
    if isinstance(value, dict):
        ordered = []
        for key in ('value','label','name','title','display','text','content','description','place','city','country','type','unit','date','begin','end','credit'):
            if key in value:
                ordered.extend(flatten_field(value.get(key)))
        if ordered:
            return ordered
        for _, v in value.items():
            ordered.extend(flatten_field(v))
        return [p for p in ordered if p]
    return [str(value)]

def render_lines(value):
    parts = []
    seen = set()
    for item in flatten_field(value):
        text = ' '.join(str(item).split()).strip(' ·;')
        if text and text not in seen:
            parts.append(text)
            seen.add(text)
    return parts

def render_text_block(value, css_class='detail-text', empty='Informazione non disponibile'):
    lines = render_lines(value)
    if not lines:
        return ''
    return '<div class="%s">%s</div>' % (css_class, '<br>'.join(safe(x) for x in lines))

def render_compact_block(value, css_class='detail-meta', empty='Informazione non disponibile'):
    lines = render_lines(value)
    if not lines:
        return ''
    return '<div class="%s">%s</div>' % (css_class, ' · '.join(safe(x) for x in lines))

def visualizza_datazione(valore):
    """Legge gli intervalli temporali dei JSON Rijksmuseum senza interpretare valori mancanti."""
    if isinstance(valore, list):
        intervalli = []
        for item in valore:
            if not isinstance(item, dict):
                continue
            earliest = item.get('earliest_start', [])
            latest = item.get('latest_end', [])
            if not isinstance(earliest, list) or not isinstance(latest, list):
                continue
            if not earliest or not latest:
                continue
            a = str(earliest[0])[:4]
            b = str(latest[-1])[:4]
            if a.isdigit() and b.isdigit():
                intervalli.append(a if a == b else a + '–' + b)
        if intervalli:
            return ' · '.join(intervalli)
    return valore

def render_opera_in_preparazione(obj, index):
    # Terza schermata: legge SOLO il file ricevuto dal Consumer gia verificato.
    number = str(obj.get('inventory_numbers', ''))
    title = str(obj.get('titles', 'Opera'))
    img_path = IMAGE_DIR / (number + '.jpg')
    if img_path.is_file() and not img_path.is_symlink() and img_path.stat().st_size > 20:
        image_main = f'<img src="/image/{index}" alt="{safe(title)}" loading="eager">'
        image_small = f'<img src="/image/{index}" alt="{safe(title)}" loading="lazy">'
    else:
        image_main = '<div class="detail-image-placeholder"><span class="detail-placeholder-mark">✦</span><span>Immagine non disponibile</span></div>'
        image_small = '<div class="detail-card-preview detail-card-preview--empty"><span class="detail-placeholder-mark">✦</span></div>'

    preview = ('<div class="detail-card-preview">' + image_small + '</div>') if 'img src=' in image_small else image_small
    enriched = render_text_block(obj.get('enriched_description'), 'detail-card-enriched')
    facts = ''.join([
        render_text_block(obj.get('object_types'), 'detail-fact'),
        render_text_block(obj.get('descriptions'), 'detail-fact'),
        render_text_block(obj.get('materials'), 'detail-fact'),
        render_text_block(obj.get('dimensions') if str(obj.get('dimensions', '')).strip().lower() != 'height 0 x width 0' else None, 'detail-fact'),
        render_text_block(obj.get('production_places'), 'detail-fact'),
        render_text_block(obj.get('credit_line'), 'detail-fact')
    ])
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe(title)} · Rijksmuseum Data Space</title><link rel="stylesheet" href="/style.css"></head>
    <body class="detail-page"><header class="detail-header"><a class="detail-brand" href="/gallery" aria-label="Torna alla galleria">R<span>·</span> Rijksmuseum <small>DATA SPACE</small></a><a class="detail-home" href="/gallery">← Torna alla galleria</a></header>
    <main class="detail-layout"><section class="detail-stage"><div class="detail-stage-head"><span class="detail-eyebrow">SCHEDA DELL'OPERA</span></div><div class="detail-stage-figure">{image_main}</div></section>
    <aside class="detail-panel"><div class="detail-card">{render_compact_block(obj.get('inventory_numbers'), 'detail-card-number')}{render_text_block(obj.get('titles'), 'detail-card-title')}{render_compact_block(obj.get('creators'), 'detail-card-creator')}{render_compact_block(visualizza_datazione(obj.get('production_dates')), 'detail-card-date')}{preview}
    <div class="detail-divider"></div>{enriched}
    <div class="detail-facts">{facts}</div></div></aside></main></body></html>'''
