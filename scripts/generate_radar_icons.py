"""Ícones monocromáticos dos temas de solicitação do Radar (gpt-image-2.5-sunburst, via OpenAI direta).

Uso: .venv/bin/python scripts/generate_radar_icons.py [--refazer] [chave ...]
Arquivo: static/images/radar-tipos/{chave}.png (256x256, preto com transparência; a interface pinta com `mask`).
"""
import argparse
import base64
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

OUT = ROOT / 'aicentralv2' / 'static' / 'images' / 'radar-tipos'
TEMPLATE = (
    "A single minimalist app icon glyph: {subject}. Monoline outline style, uniform rounded stroke, "
    "pure black on a pure white background, NO colors, NO gradients, NO shading, NO shadows, NO text, NO letters, NO numbers. "
    "Centered with generous margin, simple enough to read at 24px, a little distinctive and custom-drawn rather than a generic stock symbol."
)
ICONS = {
    'concorrentes': "a magnifying glass over two overlapping chevrons / a small podium, evoking competitor watching",
    'midia': "a browser window with a tiny play triangle and a signal wave, evoking programmatic media and connected TV",
    'logistica': "a delivery truck with a route line curving to a pin, evoking transport and logistics",
    'consumo': "a lightbulb with a small coin inside it, evoking energy bills and conscious consumption",
    'investimento': "a rising bar chart with a small arrow and a coin, evoking investment and capital",
    'regulacao': "a document with a folded corner and a small balance scale, evoking rules and regulation",
    'pauta': "a notepad page with a pencil and a small spark, evoking a content idea",
    'tendencias': "a pulse line crossing a small radar sweep arc, evoking trends and rising searches",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('keys', nargs='*')
    parser.add_argument('--refazer', action='store_true')
    args = parser.parse_args()
    from run import app
    from aicentralv2.services import openrouter_service as svc
    OUT.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        for key in args.keys or ICONS:
            target = OUT / f'{key}.png'
            if target.exists() and not args.refazer:
                continue
            result = svc._openai_generate_image({'prompt': TEMPLATE.format(subject=ICONS[key]), 'aspect_ratio': '1:1', 'quality': 'medium'},
                                                image_model='gpt-image-2.5-sunburst', output_format='png', timeout=180, size='1024x1024')
            gray = Image.open(io.BytesIO(base64.b64decode(result['b64_json']))).convert('L')
            alpha = gray.point(lambda v: 255 - v).resize((256, 256), Image.LANCZOS)
            icon = Image.new('RGBA', alpha.size, (0, 0, 0, 0))
            icon.putalpha(alpha)
            icon.save(target, optimize=True)
            print('ok', key, flush=True)


if __name__ == '__main__':
    main()
