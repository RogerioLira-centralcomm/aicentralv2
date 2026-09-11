"""Coleta de material: texto, URL e PDF."""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from typing import Optional

import requests


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
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "CentralX Smart Planner/1.0"},
    )
    response.raise_for_status()
    parser = _TextExtractor()
    parser.feed(response.text)
    text = parser.text()
    if len(text) < 40:
        raise ValueError("Não encontramos texto suficiente nesta página.")
    return text[:40000]


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
    text = "\n".join(parts).strip()
    if len(text) < 40:
        raise ValueError("Não extraímos texto suficiente do PDF.")
    return text[:40000]


def compose_material(text: str, references: Optional[list[dict]] = None) -> str:
    blocks = []
    if (text or "").strip():
        blocks.append("## Briefing do usuário\n" + text.strip())
    for item in references or []:
        kind = item.get("kind") or "referencia"
        label = item.get("name") or item.get("url") or kind
        body = (item.get("text") or "").strip()
        if body:
            blocks.append(f"## Referência ({kind}: {label})\n{body}")
    return "\n\n".join(blocks).strip()


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
