"""Gera as 4 imagens de cada estratégia de mídia pela OpenRouter, sem debitar créditos do Studio.

Imagens: conceito (visão da estratégia), criativo-topo (criativo modelo de descoberta),
criativo-conversao (criativo modelo do destino de conversão) e apoio (momento do público).
Saem em aicentralv2/static/images/estrategias/<slug>/<nome>.webp, 1200x800.
Pula o que já existe; --force refaz.

Uso:
  python scripts/gerar_imagens_estrategias.py [--slug a,b] [--force] [--workers 4] [--dry-run]

Custa dinheiro real na conta OpenRouter (cerca de US$ 0,04 a 0,08 por imagem).
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

SAIDA = ROOT / "aicentralv2" / "static" / "images" / "estrategias"
LARGURA, ALTURA = 1200, 800

ESTILO = ("Brazilian setting and people. Contemporary, premium, optimistic. Soft natural light, shallow depth of field. "
          "Color accents in emerald green (#087765) and teal, clean composition with breathing room. "
          "Absolutely no readable text, no letters, no numbers, no real brand logos or app names; "
          "any screen UI must be generic with abstract placeholder shapes instead of words.")

TELA_DESTINO = {
    "landing": "a laptop on a desk showing a clean landing page with a hero image and a short sign-up form made of blank fields",
    "site": "a smartphone showing a generic e-commerce product page with a product photo, a price tag shape and a big green buy button",
    "whatsapp": "a hand holding a smartphone with a generic green chat app conversation between a customer and a store, message bubbles without readable text",
    "formulario": "a smartphone showing a short in-app lead form with three blank fields and a green submit button over a blurred video ad",
    "app": "a smartphone showing a generic app store install screen with an app icon and a green install button",
    "loja": "a storefront on a Brazilian street with a phone in the foreground showing a map pin route to the store",
    "marketplace": "a laptop showing a generic marketplace product listing grid with one highlighted sponsored product",
}

TELA_CANAL = {
    "Sociais": "a smartphone showing a vertical short video ad in a generic social feed",
    "Streaming": "a smart TV in a living room playing a premium video ad, with a QR code shape in the corner",
    "DOOH": "a large digital billboard screen in a busy Brazilian urban street showing a bold visual ad",
    "Portais": "a tablet showing a news portal homepage with a large premium display ad takeover",
    "Programática": "a laptop and phone showing display banner ads across different generic websites",
    "Mobilidade": "a smartphone inside a ride-hailing car showing an in-app banner ad during the trip",
    "Busca": "a smartphone showing generic search results with a sponsored result highlighted in green",
    "Interativos": "a smartphone showing an interactive rich media quiz ad with tappable cards",
    "Dados": "abstract audience segments as glowing clusters of people silhouettes",
}


def prompts(e: dict, canais: dict) -> dict:
    cena = e.get("cena") or e["nome"]
    fluxo = e.get("fluxo") or []
    primeiro = next((s for et in fluxo for s in et.get("nos") or [] if s in canais), None)
    categoria = (canais.get(primeiro) or {}).get("categoria") or "Sociais"
    tela_topo = TELA_CANAL.get(categoria, TELA_CANAL["Sociais"])
    destino = (e.get("conversao") or {}).get("destino") or "site"
    tipos = sorted({(canais.get(c["slug"]) or {}).get("categoria") or "" for c in e.get("canais") or [] if c.get("peso")} - {""})
    return {
        "conceito": (f"Conceptual editorial illustration of a multi-channel media journey for: {cena}. "
                     f"A flowing luminous path connects the touchpoints ({', '.join(tipos) or 'social, search'}) as devices and places, "
                     f"ending in a conversion moment. Isometric-inspired, refined 3D render. {ESTILO}"),
        "criativo-topo": (f"Photorealistic mockup of an advertising creative for the discovery stage: {tela_topo}. "
                          f"The ad visual itself shows: {cena}. Fictional brand. {ESTILO}"),
        "criativo-conversao": (f"Photorealistic mockup of the conversion step: {TELA_DESTINO.get(destino, TELA_DESTINO['site'])}. "
                               f"Context: {cena}. Fictional brand. {ESTILO}"),
        "apoio": f"Authentic lifestyle photograph: {cena}. Candid moment, real people, editorial quality. {ESTILO}",
    }


def para_webp(b64: str) -> bytes:
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    escala = max(LARGURA / img.width, ALTURA / img.height)
    img = img.resize((round(img.width * escala), round(img.height * escala)), Image.LANCZOS)
    x, y = (img.width - LARGURA) // 2, (img.height - ALTURA) // 2
    img = img.crop((x, y, x + LARGURA, y + ALTURA))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=80, method=6)
    return out.getvalue()


def gerar(app, slug: str, nome: str, prompt: str, modelo: str) -> tuple[str, str, str]:
    from aicentralv2.services import openrouter_service as ors
    destino = SAIDA / slug / f"{nome}.webp"
    with app.app_context():
        for tentativa in range(3):
            try:
                payload = ors.build_image_payload(prompt, aspect_ratio="3:2", quality="medium", output_format="png",
                                                  resolution="1K", model=modelo)
                r = ors._openrouter_generate_image(payload, image_model=payload["model"], output_format="png", timeout=180)
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(para_webp(r["b64_json"]))
                return slug, nome, f"ok ({destino.stat().st_size // 1024} KB, {r.get('model')})"
            except Exception as exc:  # noqa: BLE001
                erro = str(exc)
                time.sleep(4 * (tentativa + 1))
    return slug, nome, f"ERRO: {erro}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="")
    args = ap.parse_args()

    from aicentralv2 import create_app
    from aicentralv2.estrategias import repositorio, visao
    from aicentralv2.services import openrouter_service as ors

    app = create_app()
    with app.app_context():
        todas, _ = repositorio.listar(somente_ativas=False)
        canais = visao.canais_catalogo()
        modelo = args.model or ors.resolve_image_model()
    filtro = {s.strip() for s in args.slug.split(",") if s.strip()}
    tarefas = []
    for e in todas:
        if filtro and e["slug"] not in filtro:
            continue
        for nome, prompt in prompts(e, canais).items():
            if not args.force and (SAIDA / e["slug"] / f"{nome}.webp").is_file():
                continue
            tarefas.append((e["slug"], nome, prompt))
    print(f"{len(tarefas)} imagem(ns) a gerar com {modelo} via OpenRouter.")
    if args.dry_run:
        for slug, nome, prompt in tarefas[:8]:
            print(f"- {slug}/{nome}: {prompt[:160]}…")
        return
    erros = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futuros = [pool.submit(gerar, app, s, n, p, modelo) for s, n, p in tarefas]
        for i, f in enumerate(as_completed(futuros), start=1):
            slug, nome, status = f.result()
            erros += status.startswith("ERRO")
            print(f"[{i}/{len(tarefas)}] {slug}/{nome}: {status}", flush=True)
    print(f"Fim: {len(tarefas) - erros} ok, {erros} erro(s).")


if __name__ == "__main__":
    main()
