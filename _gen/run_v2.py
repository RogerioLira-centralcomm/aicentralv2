"""Segunda passada das capas: prompts v2 (variedade de cena, verde só em objeto), mesmo caminho do Studio."""
import base64, io, json, sys, time
sys.path.insert(0, '_gen')
from PIL import Image
from run import app
from aicentralv2.services import openrouter_service as svc
import v2_cores as v

ONLY = set(sys.argv[1].split(',')) if len(sys.argv) > 1 and sys.argv[1] != 'all' else None
VARIANTS = (sys.argv[2] if len(sys.argv) > 2 else 'a,b').split(',')
DEST = sys.argv[3] if len(sys.argv) > 3 else 'aicentralv2/static/images/canais/capas'
with app.app_context():
    for slug, name, cat, show, text, core in v.V2:
        if ONLY and slug not in ONLY:
            continue
        text_rule = (f'If a headline is requested, render exactly this string and nothing else: "{text}".' if text else 'Render no readable text anywhere.')
        prompt = v.TEMPLATE.format(core=core, text_rule=text_rule)
        for var in VARIANTS:
            out = f'{DEST}/{slug}-{var}.webp'
            t0 = time.time()
            try:
                res = svc._openai_generate_image({'prompt': prompt, 'aspect_ratio': '16:9', 'quality': 'medium'},
                                                 image_model='gpt-image-2.5-sunburst', output_format='png', timeout=180, size='1680x944')
                Image.open(io.BytesIO(base64.b64decode(res['b64_json']))).convert('RGB').save(out, 'WEBP', quality=85)
                print('OK', slug, var, f'{time.time()-t0:.0f}s', flush=True)
            except Exception as exc:
                print('ERRO', slug, var, repr(exc)[:160], flush=True)
