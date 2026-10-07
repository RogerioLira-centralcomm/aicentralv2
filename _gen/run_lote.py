"""Gera as capas do lote 1 pelo mesmo caminho do Studio (OpenAI direta, gpt-image-2.5-sunburst)."""
import base64, csv, io, json, sys, time
from PIL import Image
from run import app
from aicentralv2.services import openrouter_service as svc

SLUGS = sys.argv[1].split(',')
VARIANTS = sys.argv[2].split(',')
QUALITY = sys.argv[3] if len(sys.argv) > 3 else 'medium'
TEMPLATE = (
 "You are rendering a finished editorial photograph for an advertising media catalog. Follow the brief literally; never add logos, brand names or readable text that were not requested.\n\n"
 "TASK: One wide 16:9 photograph used as the cover of a media channel card.\n"
 "SUBJECT AND COMPOSITION: {core}\n"
 "STYLE: realistic commercial photography, natural light, shallow depth of field, clean modern composition, a subtle emerald green accent (#1DBF73) somewhere in the scene (clothing, object or light), neutral warm skin tones, no heavy filters.\n"
 "TEXT ON SCREENS AND SURFACES: any screen or surface may show only abstract shapes and layout blocks. {text_rule}\n"
 "BRAND: the only brand shown is the fictional advertiser VÉRTICE (outdoor sportswear, simple mountain-peak mark in white). No real logos, trademarks, app icons or interface chrome from any real service.\n"
 "AVOID: real brand logos, recognizable celebrities, distorted hands, extra fingers, garbled text, watermarks, collage borders, stock-photo cliches, dark muddy shadows."
)
rows = {r['slug']: r for r in csv.DictReader(open('docs/prompts-capas-canais-image-2-5.csv'))}
with app.app_context():
    for slug in SLUGS:
        row = rows[slug]
        text_rule = (f'If a headline is requested, render exactly this string and nothing else: "{row["texto_exato"]}".' if row['texto_exato'] else 'Render no readable text anywhere.')
        prompt = TEMPLATE.format(core=row['prompt_nucleo_en'], text_rule=text_rule)
        for v in VARIANTS:
            out = f'aicentralv2/static/images/canais/capas/{slug}-{v}.webp'
            started = time.time()
            try:
                res = svc._openai_generate_image({'prompt': prompt, 'aspect_ratio': '16:9', 'quality': QUALITY},
                                                 image_model='gpt-image-2.5-sunburst', output_format='png', timeout=180, size='1680x944')
                img = Image.open(io.BytesIO(base64.b64decode(res['b64_json']))).convert('RGB')
                img.save(out, 'WEBP', quality=85)
                json.dump({'slug': slug, 'variant': v, 'model': res.get('model'), 'quality': QUALITY, 'size': img.size, 'usage': res.get('usage'), 'prompt': prompt},
                          open(out.replace('.webp', '.json'), 'w'), ensure_ascii=False, indent=1)
                print('OK', slug, v, img.size, f'{time.time()-started:.0f}s', res.get('usage'), flush=True)
            except Exception as exc:  # report and continue with the next one
                print('ERRO', slug, v, repr(exc)[:200], flush=True)
