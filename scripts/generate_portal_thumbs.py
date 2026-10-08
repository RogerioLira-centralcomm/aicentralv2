"""Ilustrações 3D dos portais para a vitrine (mesmo caminho do Studio: OpenAI direta, gpt-image-2.5-sunburst).

Uso:
  python scripts/generate_portal_thumbs.py --top            # Top 10 nacional (prompts curados abaixo)
  python scripts/generate_portal_thumbs.py --domain r7.com  # um portal
  python scripts/generate_portal_thumbs.py --limit 40       # os mais bem ranqueados que ainda não têm ilustração (prompt automático)
Regras: sem texto, sem logo e sem pessoas na imagem; o nome e o logo entram na interface, e a vitrine mostra a etiqueta "Ilustração".
Arquivo: static/images/portais/thumbs/{portal_id}.webp (1680x944). Custo medido: ~US$ 0,01 por imagem.
"""
import argparse
import base64
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

THUMBS = ROOT / 'aicentralv2' / 'static' / 'images' / 'portais' / 'thumbs'
TEMPLATE = (
    "Create a polished 3D illustration (stylized soft-clay / glossy plastic 3D render, rounded friendly shapes, soft studio lighting, subtle depth of field, "
    "clean uncluttered composition, similar to premium app onboarding art) used as the cover thumbnail of a news portal card.\n"
    "PORTAL PERSONALITY: {core}\n"
    "COLOR: dominant brand accent {accent}, supported by neutral light background and small touches of emerald green #1DBF73.\n"
    "COMPOSITION: wide 16:9, main objects centered-right, generous soft background, leave the lower-left calm.\n"
    "STRICT RULES: render NO text, NO letters, NO numbers, NO logos, NO brand marks, NO real people or faces; screens show only abstract shapes."
)
# domain -> (what makes the portal itself, brand accent colour)
CURATED = {
    'g1.globo.com': ("Brazilian general-news portal with fast breaking news and election coverage: a stylized 3D news desk with a vintage microphone, a glowing breaking-news beacon light, a floating 3D map of Brazil, a ballot box with a ballot slipping in, floating rounded news cards.", 'vivid red'),
    'ge.globo.com': ("Brazilian sports portal about football: a glossy 3D football on a green pitch with a rolling motion trail, a golden trophy, a pair of football boots, small stadium floodlights and floating scoreboard-like blocks, a hint of yellow and green.", 'vivid green'),
    'metropoles.com': ("News portal from Brasilia, the Brazilian capital, with politics and city life: the iconic Congresso Nacional twin towers with the dome and bowl in modernist 3D clay style, the curved arches of the cathedral in the background, floating rounded news cards, a small microphone.", 'bold crimson red'),
    'terra.com.br': ("Internet portal and services hub named after planet Earth: a glossy 3D planet Earth globe orbiting small floating app icons such as envelope mail, sun weather cloud, play button, shopping bag and chat bubble, all abstract and unbranded.", 'warm orange'),
    'uol.com.br': ("Brazil's biggest internet portal, a one-stop hub of news, entertainment, mail and shopping: a big glossy 3D envelope opening with colorful floating cards, a smartphone, a shopping bag, a play button and a news ticker made of abstract blocks.", 'sunny yellow'),
    'oglobo.globo.com': ("Rio de Janeiro newspaper, a traditional Brazilian daily: the Sugarloaf mountain and the Christ the Redeemer statue in 3D clay style over Guanabara Bay, a rolled newspaper and a vintage microphone in the foreground, floating rounded news cards.", 'deep ocean blue'),
    'folha.uol.com.br': ("Sao Paulo newspaper with analytical journalism: Avenida Paulista skyline with the wavy Copan building in 3D clay style, a stack of folded newspapers, a magnifying glass over an abstract chart, floating rounded news cards.", 'navy blue'),
    'estadao.com.br': ("Sao Paulo's traditional historic newspaper: the Octavio Frias cable-stayed bridge in 3D clay style, a classic rotary printing press with a ribbon of paper, a stack of rolled newspapers and a fountain pen.", 'ink blue and charcoal'),
    'cnnbrasil.com.br': ("24-hour international news channel: a 3D broadcast studio with a TV camera on a tripod, a glass globe, a big wall clock and a glowing breaking-news tower light, floating rounded video cards.", 'bold red'),
    'r7.com': ("Portal of a Brazilian TV network, video and entertainment plus news: a glossy 3D retro television set with a play button, a clapperboard, a popcorn bucket, a microphone and floating rounded video cards.", 'cobalt blue'),
}
TOP = ('g1.globo.com', 'uol.com.br', 'oglobo.globo.com', 'folha.uol.com.br', 'estadao.com.br',
       'cnnbrasil.com.br', 'r7.com', 'metropoles.com', 'terra.com.br', 'ge.globo.com')


def automatic_prompt(portal):
    place = {'Norte': 'the Brazilian Amazon region', 'Nordeste': 'the Brazilian Northeast coast', 'Sudeste': 'southeastern Brazil',
             'Sul': 'southern Brazil', 'Centro-Oeste': 'central Brazil'}
    category = str(portal.get('category') or '')
    region = next((text for key, text in place.items() if key in category), 'Brazil')
    topic = category.split('·')[0].strip() or 'news'
    uf = f" in the state of {portal['uf']}" if portal.get('uf') else ''
    return (f"A Brazilian online news portal about {topic.lower()} from {region}{uf}: 3D clay-style landmarks and scenery typical of that place, "
            "a rolled newspaper, a vintage microphone and floating rounded news cards."), 'fresh emerald green'


def select(args):
    from aicentralv2.cadu_family import repository
    if args.top:
        return repository.rows("SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p WHERE active AND domain = ANY(%s)", (list(TOP),))
    if args.domain:
        return repository.rows("SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p WHERE active AND domain = %s", (args.domain,))
    return repository.rows("""SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p
                              WHERE active ORDER BY popularity_rank ASC NULLS LAST, name LIMIT %s""", (args.limit * 3,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', action='store_true')
    parser.add_argument('--domain')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--refazer', action='store_true', help='regera mesmo que já exista')
    args = parser.parse_args()
    if not (args.top or args.domain or args.limit):
        parser.error('use --top, --domain ou --limit')
    from run import app
    from aicentralv2.services import openrouter_service as svc
    THUMBS.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        done = 0
        for portal in select(args):
            target = THUMBS / f"{portal['id']}.webp"
            if target.exists() and not args.refazer:
                continue
            if args.limit and done >= args.limit:
                break
            core, accent = CURATED.get(portal['domain']) or automatic_prompt(portal)
            started = time.time()
            try:
                result = svc._openai_generate_image({'prompt': TEMPLATE.format(core=core, accent=accent), 'aspect_ratio': '16:9', 'quality': 'medium'},
                                                    image_model='gpt-image-2.5-sunburst', output_format='png', timeout=180, size='1680x944')
                Image.open(io.BytesIO(base64.b64decode(result['b64_json']))).convert('RGB').save(target, 'WEBP', quality=85)
                done += 1
                print('ok', portal['domain'], f'{time.time() - started:.0f}s', flush=True)
            except Exception as exc:  # report and keep going: one failure must not stop the batch
                print('erro', portal['domain'], repr(exc)[:160], flush=True)


if __name__ == '__main__':
    main()
