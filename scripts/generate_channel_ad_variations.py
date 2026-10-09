"""Variações de anúncio por canal (mockups no formato real de cada app), via OpenAI direta (gpt-image-2.5-sunburst).

Uso: .venv/bin/python scripts/generate_channel_ad_variations.py [--refazer] [chave ...]
Arquivo: static/images/channel-creatives/{canal}-{formato}.jpg. Marcas de exemplo: Coca-Cola, Dove, Nescau, Itambé, Danone; sem logos dos apps.
"""
import argparse
import base64
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

OUT = ROOT / 'aicentralv2' / 'static' / 'images' / 'channel-creatives'
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from aicentralv2.cadu_planner.channel_ads import BRANDS, CHANNEL_ADS, OVERRIDES, brand_for  # noqa: E402

STYLE = "Photorealistic advertising mockup, premium, clean, legible short Portuguese text only, no watermarks. "
NINETY = "Visual language of a Brazilian ride-hailing app with a bright yellow (#FFDD00) and dark navy palette, friendly rounded UI (do not show the app's own logo). "
UBER = "Visual language of a global ride-hailing app: pure black and white UI, minimal, sharp, small green accents (do not show the app's own logo). "
COKE, DOVE, NESCAU, ITAMBE, DANONE = (brand[1] for brand in BRANDS[:5])
ADS = {
    '99-banner-home': (1024, 1536, NINETY + f"A smartphone screen (portrait) showing the app home map with a wide sponsored banner card above the ride options advertising {COKE}. " + STYLE),
    '99-cupom-corrida': (1024, 1536, NINETY + f"A smartphone screen on the ride-request step with a native coupon card from {DOVE}: 'Leve um Dove com 20% off', and a yellow request button. " + STYLE),
    '99-espera-motorista': (1024, 1536, NINETY + f"A smartphone screen while waiting for the driver: map with the car approaching, and a full-width sponsored card below showing a video still of {DANONE}. " + STYLE),
    '99-adesivo-frota': (1536, 1024, f"Street scene in a Brazilian city: a yellow-accented ride-hailing car with a full-body vinyl wrap advertising {NESCAU}, golden hour. " + STYLE),
    '99-food-patrocinado': (1024, 1536, NINETY + f"A smartphone screen of a food-delivery tab inside the app with a sponsored carousel card of {ITAMBE}, 'Patrocinado' label. " + STYLE),
    'uber-journey-ads': (1024, 1536, UBER + f"A smartphone screen during the trip: map with route and a rich sponsored card for {DOVE} with a photo and a 'Saiba mais' button. " + STYLE),
    'uber-eats-patrocinado': (1024, 1536, UBER + f"A smartphone screen of a food-delivery home with a top sponsored banner for {NESCAU} and a 'Patrocinado' tag. " + STYLE),
    'uber-topper-carro': (1536, 1024, f"Night city street: a black sedan with a rooftop digital display showing an ad for {COKE}, bright and sharp, shallow depth of field. " + STYLE),
    'uber-reserva-viagem': (1024, 1536, UBER + f"A smartphone screen on the ride-confirmation step with a clean sponsored card below the price options promoting {DANONE}, black button. " + STYLE),
    'uber-recibo-email': (1024, 1536, UBER + f"A smartphone showing a trip receipt email with a banner ad slot for {ITAMBE} at the bottom, white background. " + STYLE),
}
# Every other channel comes from channel_ads.CHANNEL_ADS (brands rotate with the channel's position, as on the page).
for _index, (_slug, (_style, _items)) in enumerate(CHANNEL_ADS.items()):
    for _position, (_key, _orientation, _title, _fmt, _text, _scene) in enumerate(_items):
        ADS[f'{_slug}-{_key}'] = ((1024, 1536) if _orientation == 'p' else (1536, 1024)) + (
            f"{_style} Scene: {_scene}, advertising {brand_for(_slug, _key, _position)[1]}. {STYLE}",)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('keys', nargs='*')
    parser.add_argument('--refazer', action='store_true')
    args = parser.parse_args()
    from run import app
    from aicentralv2.services import openrouter_service as svc
    OUT.mkdir(parents=True, exist_ok=True)
    keys = [key for key in (args.keys or ADS) if args.refazer or not (OUT / f'{key}.jpg').exists()]

    def make(key):
        width, height, prompt = ADS[key]
        try:
            with app.app_context():
                result = svc._openai_generate_image({'prompt': prompt, 'aspect_ratio': '2:3' if height > width else '3:2', 'quality': 'medium'},
                                                    image_model='gpt-image-2.5-sunburst', output_format='png', timeout=240, size=f'{width}x{height}')
            image = Image.open(io.BytesIO(base64.b64decode(result['b64_json']))).convert('RGB')
            image.thumbnail((1200, 1200), Image.LANCZOS)
            image.save(OUT / f'{key}.jpg', quality=86, optimize=True)
            print('ok', key, flush=True)
        except Exception as error:  # one failure must not stop the batch; rerun fills the gaps
            print('falhou', key, error, flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(make, keys))


if __name__ == '__main__':
    main()
