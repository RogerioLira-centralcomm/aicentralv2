"""Prints reais de telas internas dos portais: uma matéria e uma editoria (a home já é capturada por capture_portal_prints.py).

Uso (com o ambiente do app; usa a chave do Firecrawl guardada nas integrações):
  python scripts/capture_portal_inner_prints.py --curados            # os ~50 portais com perfil curado
  python scripts/capture_portal_inner_prints.py --domain g1.globo.com
Os links vêm da home renderizada: a matéria é o primeiro link com cara de reportagem; a editoria, a primeira seção conhecida.
Página quase toda em branco (anúncio ou conteúdo que não carregou) é refeita com espera maior; se continuar vazia, não é salva.
Fica 'pendente' até a aprovação (capture_portal_prints.py --aprovar-todos). Arquivos: static/images/portais/prints/{id}/{AAAAMMDD}-{tipo}.webp.
"""
import argparse
import io
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from aicentralv2 import create_app  # noqa: E402
from aicentralv2.db import get_db  # noqa: E402

STATIC = ROOT / 'aicentralv2' / 'static'
PAUSE_SECONDS = 3
SECTION_WORDS = ('politica', 'economia', 'esporte', 'noticias', 'brasil', 'mundo', 'saude', 'tecnologia', 'entretenimento', 'cultura', 'educacao',
                 'ciencia', 'opiniao', 'cidades', 'receitas', 'futebol', 'carros', 'viagem', 'moda', 'musica', 'ultimas')
SKIP = re.compile(r'/(tag|tags|autor|autores|busca|search|login|assine|newsletter|contato|sobre|politica-de|termos|privacidade|rss|feed|wp-|cdn-cgi|videos?|podcasts?|ao-vivo)(/|$)|\.(jpg|png|webp|pdf|xml)$', re.I)


def api_key():
    from aicentralv2.services.integration_credentials import resolve_firecrawl_api_key
    key = resolve_firecrawl_api_key()
    if not key:
        raise SystemExit('Sem chave do Firecrawl configurada.')
    return key


def scrape(url, formats, key, wait=4000):
    response = requests.post('https://api.firecrawl.dev/v2/scrape', timeout=150, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                             json={'url': url, 'formats': formats, 'waitFor': wait})
    response.raise_for_status()
    return response.json().get('data') or {}


def pick_links(domain, links):
    """(article_url, section_url) among the same-site links of the home page."""
    host = domain.removeprefix('www.')
    own = []
    for link in links:
        parsed = urlparse(link)
        if parsed.scheme in ('http', 'https') and (parsed.hostname or '').removeprefix('www.') == host and not SKIP.search(parsed.path):
            own.append(parsed)
    article = next((p for p in own if len([s for s in p.path.split('/') if s]) >= 2 and len(p.path) >= 35 and p.path.count('-') >= 3), None)
    section = next((p for p in own if len([s for s in p.path.strip('/').split('/') if s]) == 1 and any(word in p.path.lower() for word in SECTION_WORDS)), None)
    return (article.geturl() if article else None), (section.geturl() if section else None)


def probe_section(domain, names):
    """The home page only lists articles, so a section URL is guessed from the curated section names and kept if it really exists."""
    import unicodedata
    for name in names[:8]:
        slug = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()).strip('-')
        for candidate in dict.fromkeys((slug, slug.rstrip('s'))):
            url = f'https://{domain}/{candidate}/'
            try:
                reply = requests.get(url, timeout=15, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0 (compatible; CaduPlannerCatalogBot/1.0)'}, stream=True)
                final = urlparse(reply.url)
                reply.close()
                if reply.status_code == 200 and final.path.strip('/') and final.hostname and final.hostname.removeprefix('www.').endswith(domain.removeprefix('www.').split('.', 1)[-1]):
                    return reply.url
            except requests.RequestException:
                continue
    return None


def is_blank(image):
    """A capture that is mostly white or one flat colour carries no information."""
    gray = image.convert('L').resize((160, 90))
    stat = ImageStat.Stat(gray)
    light = sum(gray.histogram()[246:]) / (160 * 90)
    return stat.stddev[0] < 18 or light > 0.88


def screenshot(url, key):
    for wait in (4000, 9000):
        data = scrape(url, ['screenshot'], key, wait)
        shot = data.get('screenshot')
        if not shot:
            continue
        with urllib.request.urlopen(shot, timeout=60) as response:
            image = Image.open(io.BytesIO(response.read())).convert('RGB')
        if image.width > 1440:
            image = image.resize((1440, round(image.height * 1440 / image.width)), Image.LANCZOS)
        if not is_blank(image):
            return image
    return None


def save(portal_id, kind, source, image):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    relative = f'images/portais/prints/{portal_id}/{stamp}-{kind}.webp'
    target = STATIC / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, 'WEBP', quality=85)
    with get_db().cursor() as cur:
        cur.execute("""INSERT INTO cadu_planner_portal_prints (portal_id, kind, file_path, source_url)
                       VALUES (%s, %s, %s, %s) ON CONFLICT (portal_id, kind, file_path) DO NOTHING""", (portal_id, kind, relative, source))
    get_db().commit()
    return relative


def select(args):
    from aicentralv2.cadu_planner.portal_profiles import PROFILES
    from aicentralv2.cadu_planner.portals import TOP_PROFILES
    domains = [args.domain] if args.domain else list({**TOP_PROFILES, **PROFILES})
    with get_db().cursor() as cur:
        cur.execute("""SELECT id, domain, COALESCE(site_sections, '[]'::jsonb) AS sections FROM cadu_planner_portals p WHERE active AND domain = ANY(%s)
                          AND (%s OR NOT EXISTS (SELECT 1 FROM cadu_planner_portal_prints x WHERE x.portal_id = p.id AND x.kind = 'noticia' AND x.status <> 'descartado'))
                       ORDER BY featured_rank NULLS LAST, popularity_rank NULLS LAST""", (domains, bool(args.refazer)))
        return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--domain'); parser.add_argument('--curados', action='store_true'); parser.add_argument('--refazer', action='store_true')
    args = parser.parse_args()
    if not (args.domain or args.curados):
        parser.error('use --curados ou --domain')
    key = api_key()
    for row in select(args):
        try:
            home = scrape(f"https://{row['domain']}", ['links'], key)
            article, section = pick_links(row['domain'], home.get('links') or [])
            section = section or probe_section(row['domain'], row['sections'])
            for kind, url in (('noticia', article), ('editoria', section)):
                if not url:
                    print('sem link', row['domain'], kind); continue
                image = screenshot(url, key)
                print('ok   ' if image else 'vazia', row['domain'], kind, save(row['id'], kind, url, image) if image else url)
                time.sleep(PAUSE_SECONDS)
        except Exception as error:  # one broken site must not stop the batch
            print('falha', row['domain'], str(error)[:120])
        time.sleep(PAUSE_SECONDS)


if __name__ == '__main__':
    with create_app().app_context():
        main()
