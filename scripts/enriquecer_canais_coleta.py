"""Coleta imagens e textos oficiais dos canais (Firecrawl) e gera prévia para revisão.

Só coleta (cache bruto em tmp). Quem grava em cadu_canais é
scripts/enriquecer_canais_aplicar.py; a base é a fonte de verdade.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.gettempdir()) / "canais-coleta"
RAW = OUT / "raw"

# Páginas oficiais de mídia/anunciantes de cada canal ativo.
FONTES = {
    "99": ["https://99app.com/", "https://99app.com/empresas/"],
    "amazon-ads": ["https://advertising.amazon.com/pt-br"],
    "amazon-music": ["https://advertising.amazon.com/pt-br/solutions/products/amazon-music-advertising"],
    "cnn-brasil": ["https://www.cnnbrasil.com.br/publicidade/", "https://www.cnnbrasil.com.br/"],
    "deezer": ["https://deezer.com/br/", "https://advertising.deezer.com/"],
    "disney-plus": ["https://www.disneyadvertising.com/pt-br/", "https://www.disneyplus.com/pt-br"],
    "eletromidia": ["https://www.eletromidia.com.br/"],
    "g1-globo": ["https://comercial.globo.com/"],
    "ge-globo-esporte": ["https://comercial.globo.com/", "https://ge.globo.com/"],
    "globoplay": ["https://comercial.globo.com/", "https://globoplay.globo.com/"],
    "google-dv360": ["https://marketingplatform.google.com/about/display-video-360/"],
    "ifood": ["https://anuncie.ifood.com.br/", "https://www.ifood.com.br/"],
    "infomoney": ["https://www.infomoney.com.br/anuncie/", "https://www.infomoney.com.br/"],
    "instagram": ["https://business.instagram.com/", "https://www.facebook.com/business/ads"],
    "interativos": [],
    "kwai": ["https://www.kwai.com/", "https://ads.kwai.com/"],
    "linkedin": ["https://business.linkedin.com/pt-br/marketing-solutions/ads"],
    "logan": ["https://www.logan.com.br/"],
    "hbo-max": ["https://www.hbomax.com/br/pt"],
    "netflix": ["https://ads.netflix.com/pt-br/"],
    "paramount-plus": ["https://www.paramountplus.com/br/"],
    "podcast-ads": ["https://ads.spotify.com/pt-BR/ad-formats/podcast-ads/"],
    "prime-video": ["https://advertising.amazon.com/pt-br/solutions/products/prime-video-ads"],
    "r7": ["https://www.r7.com/", "https://comercial.record.r7.com/"],
    "samsung-tv-plus": ["https://www.samsung.com/br/tvs/samsung-tv-plus/", "https://www.samsungads.com/"],
    "sbt": ["https://www.sbt.com.br/", "https://www.sbt.com.br/comercial"],
    "experian-portal": ["https://www.serasaexperian.com.br/", "https://www.serasaexperian.com.br/solucoes/marketing/"],
    "experian-dmp": ["https://www.serasaexperian.com.br/solucoes/marketing/"],
    "spotify": ["https://ads.spotify.com/pt-BR/"],
    "techtudo": ["https://www.techtudo.com.br/", "https://comercial.globo.com/"],
    "tiktok": ["https://ads.tiktok.com/business/pt-BR/", "https://www.tiktok.com/business/pt"],
    "tudogostoso": ["https://www.tudogostoso.com.br/"],
    "twitch": ["https://twitchadvertising.tv/"],
    "uber": ["https://www.uber.com/br/pt-br/business/", "https://www.uber.com/br/pt-br/"],
    "uol": ["https://comercial.uol.com.br/", "https://www.uol.com.br/"],
    "waze": ["https://www.waze.com/ads"],
    "youtube": ["https://www.youtube.com/intl/pt-BR/ads/"],
}


def _rodar(url: str) -> subprocess.CompletedProcess:
    for _ in range(5):
        proc = subprocess.run(
            ["firecrawl", "scrape", url, "--format", "markdown,images", "--only-main-content"],
            capture_output=True, text=True, timeout=180,
        )
        if "Rate limit" not in (proc.stdout + proc.stderr):
            return proc
        time.sleep(30)
    return proc


def scrape(url: str) -> dict:
    proc = _rodar(url)
    out = proc.stdout
    ini = out.find("{")
    if proc.returncode != 0 or ini < 0:
        return {"url": url, "erro": (proc.stderr or out)[:300]}
    try:
        data = json.loads(out[ini:])
    except json.JSONDecodeError:
        return {"url": url, "erro": "json inválido"}
    meta = data.get("metadata") or {}
    return {
        "url": url,
        "titulo": meta.get("title") or "",
        "descricao": meta.get("og:description") or meta.get("description") or "",
        "og_image": meta.get("og:image") or meta.get("ogImage") or "",
        "favicon": meta.get("favicon") or "",
        "imagens": [i for i in (data.get("images") or []) if i.startswith("http")][:25],
        "markdown": (data.get("markdown") or "")[:6000],
    }


def coletar(slug: str) -> tuple[str, list[dict]]:
    paginas = [scrape(u) for u in FONTES.get(slug, [])]
    (RAW / f"{slug}.json").write_text(json.dumps(paginas, ensure_ascii=False, indent=1), encoding="utf-8")
    return slug, paginas


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    slugs = [s for s in FONTES if not only or s in only]
    with ThreadPoolExecutor(max_workers=2) as ex:
        resultados = dict(ex.map(coletar, slugs))

    for slug, paginas in resultados.items():
        ok = [p for p in paginas if not p.get("erro")]
        print(f"{slug}: {len(ok)}/{len(paginas)} páginas")


if __name__ == "__main__":
    main()
