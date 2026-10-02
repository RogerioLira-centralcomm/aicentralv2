"""Baixa imagens reais coletadas dos canais e grava em cadu_canais.

Fonte de verdade é a base: preenche `og_image_path` e `imagens` (jsonb) e, se
vazio, `imagem_path`. Nunca sobrescreve valor existente. Os arquivos vão para
aicentralv2/static/images/canais-midia/<slug>/.

Uso: enriquecer_canais_aplicar.py [--aplicar] [slug ...]   (sem --aplicar = dry-run)
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from aicentralv2.crm_v3_canais import _connect_canais_db  # noqa: E402

RAW = Path(tempfile.gettempdir()) / "canais-coleta" / "raw"
DEST = ROOT / "aicentralv2" / "static" / "images" / "canais-midia"
URL_BASE = "/static/images/canais-midia"
MAX_IMAGENS = 6
MIN_LADO = 400
RUIM = re.compile(r"logo|icon|sprite|avatar|favicon|pixel|badge|flag|\.svg|\.gif|tracking|1x1", re.I)
UA = {"User-Agent": "Mozilla/5.0 (compatible; CaduCatalogBot/1.0)"}


def candidatas(slug: str) -> tuple[str, list[str]]:
    og, urls = "", []
    arq = RAW / f"{slug}.json"
    if not arq.exists():
        return og, urls
    for pagina in json.loads(arq.read_text(encoding="utf-8")):
        og = og or pagina.get("og_image") or ""
        for u in [pagina.get("og_image") or "", *(pagina.get("imagens") or [])]:
            if u.startswith("http") and u not in urls and (u == og or not RUIM.search(u)):
                urls.append(u)
    return og, urls


def baixar(url: str, slug: str, pasta: Path) -> str | None:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        if not r.headers.get("content-type", "").startswith("image/") or len(r.content) < 15_000:
            return None
        img = Image.open(io.BytesIO(r.content))
        if min(img.size) < MIN_LADO // 2 or max(img.size) < MIN_LADO:
            return None
        rgb = img.convert("RGB")
        rgb.thumbnail((1600, 1600))
        nome = hashlib.sha1(url.encode()).hexdigest()[:10] + ".jpg"
        pasta.mkdir(parents=True, exist_ok=True)
        rgb.save(pasta / nome, "JPEG", quality=85, optimize=True)
        return f"{URL_BASE}/{slug}/{nome}"
    except Exception:
        return None


def main() -> None:
    args = sys.argv[1:]
    aplicar = "--aplicar" in args
    only = {a for a in args if not a.startswith("--")}
    conn = _connect_canais_db()
    with conn.cursor() as cur:
        cur.execute("SELECT slug, og_image_path, imagem_path, imagens FROM cadu_canais WHERE is_active ORDER BY slug")
        rows = cur.fetchall()
    for row in rows:
        slug = row["slug"]
        if only and slug not in only:
            continue
        if row["og_image_path"] and row["imagens"]:
            print(f"{slug}: já preenchido")
            continue
        og, urls = candidatas(slug)
        salvas, og_local = [], ""
        for u in urls:
            if len(salvas) >= MAX_IMAGENS:
                break
            caminho = baixar(u, slug, DEST / slug) if aplicar else ("dry" if u else None)
            if caminho:
                salvas.append(caminho)
                if u == og:
                    og_local = caminho
        print(f"{slug}: {len(urls)} candidatas, {len(salvas)} aceitas")
        if not aplicar or not salvas:
            continue
        og_local = og_local or salvas[0]
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cadu_canais SET
                  og_image_path = COALESCE(NULLIF(og_image_path, ''), %s),
                  imagem_path = COALESCE(NULLIF(imagem_path, ''), %s),
                  imagens = CASE WHEN imagens IS NULL OR imagens::text IN ('[]', 'null')
                                 THEN %s::jsonb ELSE imagens END,
                  updated_at = now()
                WHERE slug = %s
                """,
                (og_local, salvas[0], json.dumps(salvas), slug),
            )
        conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
