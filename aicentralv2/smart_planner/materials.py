"""Coleta de material: texto, URL, PDF e dossiê de apoio."""

from __future__ import annotations

import logging
import os
import re
from html.parser import HTMLParser
from typing import Optional

import requests

from .helpers import as_dict, as_list, strip_markdown, text

logger = logging.getLogger(__name__)

REFERENCE_PAPEL = {
    "url": "marca",
    "file": "campanha",
    "image": "visual",
    "search": "mercado",
}
PAPEL_VALIDOS = {"marca", "campanha", "mercado", "visual"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self._skip = False
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        raw = re.sub(r"[ \t]+", " ", "".join(self._chunks))
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def scrape_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Informe uma URL http ou https.")
    scraped = _scrape_firecrawl(url)
    if scraped:
        return scraped
    return _scrape_html(url)


def _scrape_firecrawl(url: str) -> str:
    if not (os.getenv("FIRECRAWL_API_KEY") or "").strip():
        return ""
    try:
        from ..crm_v3_web_scout import _firecrawl_scrape
        data = _firecrawl_scrape(
            url,
            formats=["markdown"],
            timeout_s=40,
            only_main_content=True,
        )
    except Exception:
        logger.exception("Firecrawl não capturou %s", url)
        return ""
    body = str((data or {}).get("markdown") or (data or {}).get("content") or "").strip()
    if len(body) < 40:
        return ""
    return body[:40000]


def _scrape_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "CentralX Smart Planner/1.0"},
    )
    response.raise_for_status()
    parser = _TextExtractor()
    parser.feed(response.text)
    extracted = parser.text()
    if len(extracted) < 40:
        raise ValueError("Não encontramos texto suficiente nesta página.")
    return extracted[:40000]


def extract_pdf(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("Extração de PDF indisponível neste servidor.") from exc
    reader = PdfReader(path)
    parts = []
    for page in reader.pages[:40]:
        parts.append(page.extract_text() or "")
    extracted = "\n".join(parts).strip()
    if len(extracted) < 40:
        raise ValueError("Não extraímos texto suficiente do PDF.")
    return extracted[:40000]


def normalize_reference(item: dict | None) -> dict:
    raw = as_dict(item)
    kind = text(raw.get("kind") or "referencia").lower()
    if kind == "pdf":
        kind = "file"
    label = text(raw.get("label") or raw.get("name") or raw.get("url") or kind)
    notas = strip_markdown(text(raw.get("notas") or raw.get("digest") or raw.get("text")))
    fatos = raw.get("fatos") if isinstance(raw.get("fatos"), dict) else {}
    papel = text(raw.get("papel")).lower()
    if papel not in PAPEL_VALIDOS:
        papel = REFERENCE_PAPEL.get(kind, "marca")
    out = {
        "kind": kind,
        "label": label,
        "notas": notas,
        "fatos": {str(key): value for key, value in fatos.items() if value not in ("", [], None)},
        "papel": papel,
    }
    if raw.get("url"):
        out["url"] = text(raw.get("url"))
    if raw.get("name"):
        out["name"] = text(raw.get("name"))
    return out


def normalize_references(references: Optional[list] = None) -> list[dict]:
    return [normalize_reference(item) for item in as_list(references) if as_dict(item)]


def compose_material(text_in: str, references: Optional[list] = None) -> str:
    blocks = []
    user = (text_in or "").strip()
    if user:
        blocks.append("Briefing do usuário\n" + user)
    for item in normalize_references(references):
        notas = item.get("notas") or ""
        if not notas:
            continue
        kind = item.get("kind") or "referencia"
        label = item.get("label") or kind
        papel = item.get("papel") or ""
        head = f"Notas de apoio ({kind}: {label})"
        if papel:
            head += f" — papel {papel}"
        blocks.append(f"{head}\n{notas}")
    return "\n\n".join(blocks).strip()


def apoio_notes(dados: dict | None, cap: int = 8000) -> str:
    fonte = as_dict(as_dict(dados).get("fonte"))
    refs = normalize_references(fonte.get("referencias") or as_dict(dados).get("referencias"))
    parts = []
    for item in refs:
        notas = item.get("notas") or ""
        if not notas:
            continue
        label = item.get("label") or item.get("url") or item.get("kind")
        papel = item.get("papel") or ""
        prefix = f"{label} ({papel}): " if papel else f"{label}: "
        parts.append(prefix + notas)
    return "\n\n".join(parts)[:cap].strip()


def apoio_block(dados: dict | None, cap: int = 8000) -> str:
    notes = apoio_notes(dados, cap=cap)
    if not notes:
        return ""
    return "\n\nApoio revisado\n" + notes


def save_upload(file_storage, dest_dir: str) -> tuple[str, str]:
    original = os.path.basename(file_storage.filename or "arquivo.pdf")
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in {"pdf", "png", "jpg", "jpeg", "webp"}:
        raise ValueError("Envie um PDF ou imagem.")
    os.makedirs(dest_dir, exist_ok=True)
    safe = f"{os.urandom(8).hex()}.{ext}"
    path = os.path.join(dest_dir, safe)
    file_storage.save(path)
    return path, original
