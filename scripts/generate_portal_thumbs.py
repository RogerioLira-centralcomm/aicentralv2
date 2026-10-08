"""Ilustrações 3D dos portais para a vitrine (mesmo caminho do Studio: OpenAI direta, gpt-image-2.5-sunburst).

Uso:
  python scripts/generate_portal_thumbs.py --top            # Top 10 nacional (prompts curados abaixo)
  python scripts/generate_portal_thumbs.py --curados        # os ~50 com prompt escrito à mão
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


CURATED.update({
    'autoesporte.globo.com': ("Car magazine portal: a glossy 3D sports car on a curved road, a tire, a steering wheel, a small trophy and floating rounded cards.", 'racing red'),
    'casaejardim.globo.com': ("Home and garden magazine: a cozy 3D living room corner with a sofa, floor lamp, big plant, watering can and a small garden with flowers.", 'sage green'),
    'revistacrescer.globo.com': ("Parenting magazine: a 3D baby crib, a stroller, a teddy bear, wooden toy blocks and a mobile with stars, soft pastel world.", 'soft pastel pink and baby blue'),
    'globo.com': ("Largest Brazilian media-group portal gathering news, sport, TV and entertainment: a glossy 3D globe in the center with floating tiles shaped like a TV, a football, a newspaper and a star.", 'ocean blue'),
    'gshow.globo.com': ("TV entertainment and soap-opera portal: a retro 3D television, a clapperboard, a red-carpet strip with a golden star, a popcorn bucket and floating video cards.", 'magenta'),
    'marieclaire.globo.com': ("Women's fashion and lifestyle magazine: a 3D designer handbag, high-heel shoes, a perfume bottle, sunglasses and a flower bouquet on a pastel podium.", 'rose pink'),
    'quem.globo.com': ("Celebrity news magazine: a red carpet with a golden star, camera flashes, a vintage microphone, sunglasses and floating gossip cards.", 'hot pink'),
    'valor.globo.com': ("Economy and business newspaper: a 3D bull and bear statuette, stacked coins, rising bar charts and the Sao Paulo financial skyline.", 'deep emerald green'),
    'vogue.globo.com': ("High-fashion magazine: an elegant 3D dress form mannequin with a flowing gown, a handbag, sunglasses and a mirror on a marble podium.", 'black and gold'),
    'band.uol.com.br': ("Brazilian TV network portal with news and sports: a 3D TV camera, a football, a news desk microphone and a small satellite dish.", 'amber orange'),
    'bol.uol.com.br': ("Classic internet portal with e-mail and entertainment: a big glossy 3D mailbox with floating envelope, news and horoscope cards and a smartphone.", 'bright blue'),
    'brasilescola.uol.com.br': ("School study portal: a stack of 3D books, a globe, a pencil, a graduation cap, a backpack and a small chalkboard with abstract diagrams.", 'sky blue'),
    'drauziovarella.uol.com.br': ("Health information portal by a famous doctor: a 3D stethoscope, a heart, a pill bottle, an apple and a clipboard with abstract charts.", 'calm teal'),
    'hugogloss.uol.com.br': ("Celebrity gossip and pop culture portal: a smartphone with a big heart reaction, camera flashes, a red carpet, a tiny star-shaped trophy and floating chat bubbles.", 'vivid purple'),
    'mundoeducacao.uol.com.br': ("Education portal for students: a 3D chalkboard with abstract formulas, a backpack, a notebook, a trophy and a lightbulb.", 'orange'),
    'rollingstone.uol.com.br': ("Rock music magazine: a 3D electric guitar, a vinyl record, a vintage microphone, an amplifier and stage lights.", 'black and rock red'),
    'letras.mus.br': ("Song lyrics portal: floating 3D musical notes, over-ear headphones, a microphone and an open lyric notebook.", 'violet purple'),
    'br.investing.com': ("Financial markets portal: 3D candlestick charts, stacked coins, a bull figurine and a ticker made of abstract blocks.", 'amber orange'),
    'claudia.abril.com.br': ("Women's lifestyle magazine: a 3D coffee cup, a planner with a pencil, flowers, a handbag and a soft pastel background.", 'coral'),
    'quatrorodas.abril.com.br': ("Car magazine: a glossy 3D SUV on a mountain road, a steering wheel, a road sign shaped abstractly and floating test-drive cards.", 'steel blue'),
    'super.abril.com.br': ("Science and curiosity magazine: a glowing 3D lightbulb, an atom, a rocket, a telescope and a planet.", 'electric blue'),
    'veja.abril.com.br': ("Weekly news magazine: a stack of 3D magazines, a magnifying glass over a map of Brazil and a pen, floating rounded cards.", 'strong red'),
    'viagemeturismo.abril.com.br': ("Travel magazine: a 3D suitcase with stickers, an airplane, a globe, palm trees and a compass on a tropical island.", 'turquoise'),
    'cifraclub.com.br': ("Guitar chord and tab portal: a 3D acoustic guitar, a ukulele, a tuner, floating sheet music and a metronome.", 'warm orange'),
    'tuasaude.com': ("Health and wellness portal: a 3D apple, a heart, a yoga mat, a glass of water, a stethoscope and green leaves.", 'fresh green'),
    'olhardigital.com.br': ("Technology news portal: a 3D robot, a drone, a smartphone, VR headset and a circuit-board pattern, floating cards.", 'electric purple'),
    'espn.com.br': ("Multi-sport portal: a 3D football, a basketball, a tennis racket, a trophy and a scoreboard made of abstract blocks.", 'bold red'),
    'ig.com.br': ("Brazilian internet portal with news, e-mail and entertainment: a glossy 3D envelope, a chat bubble, a play button and floating news cards.", 'deep purple'),
    'lance.com.br': ("Sports daily newspaper focused on football: a 3D football, boots, a folded newspaper, a whistle and a small stadium.", 'black and green'),
    'climatempo.com.br': ("Weather forecast portal: a 3D sun peeking from a cloud, raindrops, a thermometer, a wind turbine and a small Brazil weather map.", 'sky blue'),
    'ndmais.com.br': ("News portal from Florianopolis, Santa Catarina: the Hercilio Luz suspension bridge in 3D clay style over the bay, sailboats, a beach with palm and a rolled newspaper.", 'ocean blue'),
    'correio24horas.com.br': ("Salvador newspaper, Bahia: the Farol da Barra lighthouse and fort in 3D clay style, colorful ribbons of Bonfim, a drum, a rolled newspaper and a microphone.", 'bright red'),
    'tudocelular.com': ("Smartphone news and reviews portal: several glossy 3D smartphones fanned out, a camera lens, a charging cable and a benchmark chart made of blocks.", 'bright orange'),
    'nsctotal.com.br': ("News portal from Santa Catarina state: a 3D beach with a surfboard, a lighthouse, pine trees from the highlands, a rolled newspaper and a microphone.", 'deep blue'),
    'tudogostoso.com.br': ("Recipe portal: a 3D cooking pot with steam, a wooden spoon, fresh vegetables, a chef hat and a slice of cake.", 'warm red-orange'),
    'agenciabrasil.ebc.com.br': ("Brazilian public news agency: a 3D globe, a microphone, the Brasilia Congress dome and floating news cards for all regions.", 'blue and green'),
    'exame.com': ("Business and economy magazine: a 3D briefcase, a rocket taking off from a bar chart, a lightbulb and coins.", 'strong red'),
    'motor1.com': ("Car culture portal: a sleek 3D supercar and an electric car charging station, a racing helmet and a speedometer.", 'electric blue'),
    'correiobraziliense.com.br': ("Brasilia newspaper: the Juscelino Kubitschek bridge arches in 3D clay style over the lake, a rolled historic newspaper and a vintage microphone.", 'navy blue'),
    'gauchazh.clicrbs.com.br': ("News portal from Rio Grande do Sul: Porto Alegre sunset over the Guaiba lake in 3D clay style, a chimarrao gourd with bombilla, a rolled newspaper and a microphone.", 'deep blue'),
})
CURADOS = tuple(CURATED)


UF_NAMES = {'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo',
            'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba',
            'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul',
            'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'}
ACCENTS = ('fresh emerald green', 'ocean blue', 'warm orange', 'deep teal', 'coral red', 'golden yellow', 'violet purple', 'sky blue')


# National portals that are really one city's newspaper.
HOME_CITY = {
    'em.com.br': ('Belo Horizonte', 'Minas Gerais'), 'otempo.com.br': ('Belo Horizonte', 'Minas Gerais'), 'uai.com.br': ('Belo Horizonte', 'Minas Gerais'),
    'opovo.com.br': ('Fortaleza', 'Ceará'), 'atarde.com.br': ('Salvador', 'Bahia'), 'agazeta.com.br': ('Vitória', 'Espírito Santo'),
    'gazetadopovo.com.br': ('Curitiba', 'Paraná'), 'opopular.com.br': ('Goiânia', 'Goiás'), 'correiodopovo.com.br': ('Porto Alegre', 'Rio Grande do Sul'),
    'folhape.com.br': ('Recife', 'Pernambuco'),
}
# Scenes by editorial category, with no place at all, so national portals never default to the same postcard.
CATEGORY_SCENES = {
    'economia': ["a 3D bull and bear statuette, stacked gold coins, rising bar charts and a calculator on a desk", "a 3D briefcase, a piggy bank, a rocket launching from a bar chart and floating percentage-shaped cards"],
    'tecnologia': ["3D gadgets: a smartphone, a laptop, a game controller and a robot arm with circuit patterns", "a glossy 3D robot, VR headset, drone and floating app tiles"],
    'entretenimento': ["a 3D film clapperboard, a popcorn bucket, 3D glasses, a star and a spotlight", "a 3D retro TV, a golden star on a red carpet and camera flash bursts"],
    'esportes': ["a 3D football, a trophy, boots and a scoreboard", "a 3D basketball, a tennis racket, a medal and stadium lights"],
    'ciência': ["a glowing 3D lightbulb, an atom, a telescope and a rocket", "a 3D microscope, a globe and floating chemistry flasks"],
    'mulher': ["a 3D handbag, high heels, a perfume bottle and sunglasses on a pastel podium", "3D lipstick, a mirror, flowers and a shopping bag"],
    'viagem': ["a 3D suitcase with stickers, an airplane, a compass and a tropical island", "a 3D passport, a camera, a hot air balloon and a world map"],
    'saúde': ["a 3D stethoscope, a heart, an apple and a clipboard", "3D vitamin bottles, a running shoe and a water glass"],
    'automotivo': ["a glossy 3D car on a curved road, a steering wheel and a speedometer", "a 3D electric car with a charging station"],
    'música': ["a 3D electric guitar, headphones, a vinyl record and notes", "a 3D microphone, a keyboard and stage lights"],
}
NEWS_SCENES = [
    "a 3D newsroom desk with a vintage microphone, a breaking-news beacon light and a floating map of Brazil",
    "a 3D stack of folded newspapers, a magnifying glass over a chart and a fountain pen",
    "a 3D press-conference podium with several microphones and floating rounded quote cards",
    "a 3D globe with a satellite dish, a TV camera and floating news cards",
    "a 3D ballot box, a gavel, a scale of justice and floating news cards",
]


def automatic_prompt(portal):
    """Regional prompt from the portal's own city and state; national ones from their category, never from a default postcard."""
    category = str(portal.get('category') or '')
    topic = category.split('·')[0].strip().lower() or 'news'
    accent = ACCENTS[int(portal['id']) % len(ACCENTS)]
    city, state = str(portal.get('city') or '').strip(), UF_NAMES.get(str(portal.get('uf') or ''), '')
    if portal['domain'] in HOME_CITY:
        city, state = HOME_CITY[portal['domain']]
    if state:
        place = f"the city of {city}, {state}, Brazil" if city else f"the state of {state}, Brazil"
        return (f"A local Brazilian online news portal about {topic} from {place}: 3D clay-style version of the most recognizable landmarks, streets, nature or "
                "culture of that exact place, a rolled newspaper, a vintage microphone and floating rounded news cards."), accent
    scenes = next((value for key, value in CATEGORY_SCENES.items() if key in topic), NEWS_SCENES)
    scene = scenes[int(portal['id']) % len(scenes)]
    return (f"A Brazilian national online portal about {topic}: {scene}. No landmarks and no real places, only the objects, in a clean abstract studio set."), accent


def select(args):
    from aicentralv2.cadu_family import repository
    if args.top:
        return repository.rows("SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p WHERE active AND domain = ANY(%s)", (list(TOP),))
    if args.ids:
        return repository.rows("""SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf,
                                     (SELECT split_part(a->>'valor', ' · ', 1) FROM jsonb_array_elements(public_attributes) a WHERE a->>'atributo' = 'localizacao' LIMIT 1) AS city
                                FROM cadu_planner_portals p WHERE active AND id = ANY(%s)""", ([int(x) for x in args.ids.split(',')],))
    if args.curados:
        return repository.rows("SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p WHERE active AND domain = ANY(%s) ORDER BY popularity_rank ASC NULLS LAST, name", (list(CURADOS),))
    if args.domain:
        return repository.rows("SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf FROM cadu_planner_portals p WHERE active AND domain = %s", (args.domain,))
    return repository.rows("""SELECT id, domain, name, category, to_jsonb(p)->>'uf' AS uf,
                                     (SELECT split_part(a->>'valor', ' · ', 1) FROM jsonb_array_elements(public_attributes) a WHERE a->>'atributo' = 'localizacao' LIMIT 1) AS city
                                FROM cadu_planner_portals p
                               WHERE active AND popularity_source = 'tranco' AND popularity_rank IS NOT NULL
                            ORDER BY popularity_rank ASC, name LIMIT %s""", (args.limit * 3,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top', action='store_true')
    parser.add_argument('--curados', action='store_true', help='todos os portais com prompt curado que ainda não têm ilustração')
    parser.add_argument('--ids', help='ids de portais, separados por vírgula (com --refazer, regera)')
    parser.add_argument('--domain')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--workers', type=int, default=4, help='gerações em paralelo')
    parser.add_argument('--refazer', action='store_true', help='regera mesmo que já exista')
    args = parser.parse_args()
    if not (args.top or args.curados or args.domain or args.limit or args.ids):
        parser.error('use --top, --curados, --ids, --domain ou --limit')
    from run import app
    from aicentralv2.services import openrouter_service as svc
    THUMBS.mkdir(parents=True, exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor
    with app.app_context():
        todo = []
        for portal in select(args):
            if (THUMBS / f"{portal['id']}.webp").exists() and not args.refazer:
                continue
            todo.append(portal)
            if args.limit and len(todo) >= args.limit:
                break

        def generate(portal):
            target = THUMBS / f"{portal['id']}.webp"
            core, accent = CURATED.get(portal['domain']) or automatic_prompt(portal)
            started = time.time()
            try:
                with app.app_context():
                    result = svc._openai_generate_image({'prompt': TEMPLATE.format(core=core, accent=accent), 'aspect_ratio': '16:9', 'quality': 'medium'},
                                                        image_model='gpt-image-2.5-sunburst', output_format='png', timeout=180, size='1680x944')
                Image.open(io.BytesIO(base64.b64decode(result['b64_json']))).convert('RGB').save(target, 'WEBP', quality=85)
                print('ok', portal['domain'], f'{time.time() - started:.0f}s', flush=True)
            except Exception as exc:  # report and keep going: one failure must not stop the batch
                print('erro', portal['domain'], repr(exc)[:160], flush=True)

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            list(pool.map(generate, todo))


if __name__ == '__main__':
    main()
