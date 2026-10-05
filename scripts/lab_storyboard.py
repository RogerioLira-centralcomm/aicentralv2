"""A/B do diretor de storyboard (briefing -> cenas e roteiro) antes de ir ao Studio.

Só texto, sem imagem. Roda cada briefing em cada modelo e imprime uma linha JSON por execução com as
métricas automáticas; a saída completa vai para --out para leitura humana.

    .venv/bin/python scripts/lab_storyboard.py --models openai/gpt-5-nano,openai/gpt-5-mini,anthropic/claude-haiku-4.5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aicentralv2 import create_app  # noqa: E402

BRIEFINGS = [
    {"id": "telecom", "duration": 15, "ratio": "9:16", "brand": {"name": "Cemig Conecta", "tone": "próximo e direto"},
     "briefing": "Anúncio de internet fibra para famílias. Oferta: 500 mega por R$ 79,90 por mês, instalação grátis. Mostrar a família usando a internet em casa e fechar com o CTA 'Fale com a gente'."},
    {"id": "varejo", "duration": 15, "ratio": "1:1", "brand": {"name": "Casa Verde", "tone": "alegre"},
     "briefing": "Promoção de fim de semana de uma loja de jardinagem: até 30% de desconto em plantas e vasos, sábado e domingo. Mostrar plantas, vasos e a loja cheia de clientes."},
    {"id": "institucional", "duration": 8, "ratio": "16:9", "brand": {"name": "Instituto Horizonte", "tone": "inspirador"},
     "briefing": "Vídeo institucional curto de uma ONG de educação que leva reforço escolar a crianças. Sem oferta e sem preço. Emocionar e convidar a conhecer o trabalho."},
    {"id": "lancamento", "duration": 30, "ratio": "16:9", "brand": {"name": "Pulse", "tone": "moderno, tecnológico"},
     "briefing": "Lançamento do fone de ouvido Pulse X com cancelamento de ruído, bateria de 40 horas e estojo de carga. Mostrar uso na rotina: trabalho, academia e viagem. Disponível em 3 cores."},
]


def metrics(case, result):
    beats = result["beats"]
    briefing_numbers = set(re.findall(r"\d+", case["briefing"]))
    numbers = {n for b in beats for f in ("visual", "spoken") for n in re.findall(r"\d+", b[f])}
    words = sum(len(b["spoken"].split()) for b in beats)
    visuals = [set(re.findall(r"\w+", b["visual"].lower())) for b in beats]
    dup = max((len(a & b) / max(1, len(a | b)) for i, a in enumerate(visuals) for b in visuals[i + 1:]), default=0)
    brand = case["brand"]["name"].lower().split()[0]
    return {
        "cenas": len(beats),
        "abre_com_hook": beats[0]["purpose"] == "hook",
        "fecha": beats[-1]["purpose"] in {"end", "offer"},
        "numeros_inventados": sorted(numbers - briefing_numbers),
        "palavras_por_segundo": round(words / case["duration"], 2),
        "similaridade_maxima": round(dup, 2),
        "visual_medio_chars": round(sum(len(b["visual"]) for b in beats) / len(beats)),
        "cenas_com_marca": sum(1 for b in beats if brand in (b["visual"] + b["hold"]).lower()),
        "avisos": result["warnings"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="openai/gpt-5-nano,openai/gpt-5-mini,anthropic/claude-haiku-4.5")
    parser.add_argument("--out", default="output/lab-storyboard.json")
    args = parser.parse_args()
    app = create_app()
    runs = []
    with app.app_context():
        from aicentralv2.creative_media.studio_storyboard import plan_storyboard
        from aicentralv2.services.openrouter_service import chat_completion
        for case in BRIEFINGS:
            for model in args.models.split(","):
                started = time.time()
                try:
                    result = plan_storyboard(case["briefing"], duration=case["duration"], aspect_ratio=case["ratio"],
                                             brand=case["brand"], text_callable=chat_completion, model=model)
                    row = {"caso": case["id"], "modelo": model, "segundos": round(time.time() - started, 1),
                           **metrics(case, result)}
                    runs.append({**row, "beats": result["beats"]})
                except Exception as error:  # noqa: BLE001
                    row = {"caso": case["id"], "modelo": model, "erro": str(error)[:200]}
                    runs.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(runs, handle, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
