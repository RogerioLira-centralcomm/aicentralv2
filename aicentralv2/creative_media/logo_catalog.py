"""Logos oficiais de terceiros para o Studio: canais e portais do catálogo do Planner citados no pedido.

O modelo de imagem não sabe desenhar logos de memória (inventa um "X" para Exame, um círculo para UOL). Quando o
pedido cita uma plataforma do catálogo, o logo oficial entra como referência de identidade ("logo oficial de …").
"""
from __future__ import annotations

import base64
import io
import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)
STATIC = Path(__file__).resolve().parents[1] / "static"


def _plain(value):
    return unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode().lower()


GENERIC_HOSTS = {"google", "sites", "blogspot", "wordpress", "medium", "facebook", "instagram", "youtube", "linktr", "wix"}


def _names(row, first_word=False):
    """Nomes pelos quais a plataforma é citada: {nome: força}. Nome completo vale 2; primeira palavra e domínio, 1."""
    names = {}
    for part in re.split(r"[/|,()]", str(row.get("name") or "")):
        if len(part.strip()) >= 3:
            names[_plain(part).strip()] = 2
    slug = _plain(row.get("slug") or "").replace("-", " ").strip()
    if len(slug) >= 3:
        names.setdefault(slug, 2)
    if first_word:  # canal "Google Ads" também é citado como "Google"
        for name in [name for name in names if " " in name]:
            if len(name.split()[0]) >= 4:
                names.setdefault(name.split()[0], 1)
    domain = _plain(row.get("domain") or "").removeprefix("www.").split(".")[0]
    if len(domain) >= 3 and domain not in GENERIC_HOSTS:  # portal "Valor Econômico" é citado como "Valor" (valor.globo.com)
        names.setdefault(domain, 1)
    return names


def _channels():
    from ..cadu_family import repository
    from ..crm_v3_canais import _resolver_logo
    for row in repository.catalog("canais"):
        path = _resolver_logo(row.get("slug") or "", row.get("logo_path") or "")
        if path:
            yield {"name": row.get("name"), "names": _names(row, first_word=True), "path": path}


def _portals():
    from ..cadu_family import repository
    for row in repository.rows("SELECT name, domain, favicon_url FROM cadu_planner_portals WHERE name IS NOT NULL"):
        url = row.get("favicon_url") or (f"https://www.google.com/s2/favicons?domain={row['domain']}&sz=128" if row.get("domain") else "")
        if url:
            yield {"name": row.get("name"), "names": _names(row), "path": url}


_CACHE = {"at": 0.0, "entries": []}


def _entries():
    """Canais e portais do catálogo, lidos no máximo a cada 10 minutos (o catálogo muda raramente)."""
    import time
    if time.monotonic() - _CACHE["at"] > 600 or not _CACHE["entries"]:
        _CACHE["entries"], _CACHE["at"] = [*_channels(), *_portals()], time.monotonic()
    return _CACHE["entries"]


def mentioned(brief, entries):
    """Uma plataforma por nome citado no pedido (palavra inteira, sem acento): o nome completo vence domínio e apelido."""
    text = _plain(brief)
    hits = []
    for order, entry in enumerate(entries):
        matches = [(strength, name) for name, strength in entry["names"].items() if re.search(rf"\b{re.escape(name)}\b", text)]
        if matches:
            strength, name = max(matches)
            hits.append((-strength, order, name, entry))
    found, taken = [], set()
    for _, _, name, entry in sorted(hits, key=lambda item: item[:2]):
        if name in taken or any(name in other or other in name for other in taken):
            continue
        taken.add(name)
        found.append((re.search(rf"\b{re.escape(name)}\b", text).start(), entry))
    return [entry for _, entry in sorted(found, key=lambda item: item[0])]


def _png_data_url(path):
    from PIL import Image
    if path.startswith("/static/"):
        file = STATIC / path[len("/static/"):].split("?", 1)[0]
        if not file.is_file():
            return ""
        raw = file.read_bytes()
        if file.suffix.lower() == ".svg":
            import cairosvg
            raw = cairosvg.svg2png(bytestring=raw, output_width=512)
    elif path.startswith("https://"):
        import requests
        response = requests.get(path, timeout=6)
        response.raise_for_status()
        raw = response.content
    else:
        return ""
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    if max(image.size) < 256:  # favicon: amplia para o modelo ler a forma (sem inventar detalhe)
        scale = 256 / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def references(brief, limit=2):
    """Até ``limit`` referências de identidade com o logo oficial de cada plataforma citada. Nunca levanta."""
    if limit <= 0 or not str(brief or "").strip():
        return []
    try:
        entries = mentioned(brief, _entries())
    except Exception:
        logger.warning("Studio logo catalog unavailable", exc_info=True)
        return []
    out = []
    for entry in entries:
        try:
            url = _png_data_url(entry["path"])
        except Exception:
            logger.info("Studio logo for %s unavailable", entry["name"], exc_info=True)
            continue
        if url:
            out.append({"id": f"logo-{_plain(entry['name'])[:40]}", "url": url, "role": "identity", "source": "project",
                        "label": f"logo oficial de {entry['name']}",
                        "instruction": f"the official {entry['name']} logo: reproduce this exact mark faithfully where the brief places {entry['name']}"})
        if len(out) >= limit:
            break
    return out
