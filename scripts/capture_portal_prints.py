"""Captura a home real dos portais (print acima da dobra) e registra para aprovação humana.

Uso (com o ambiente do app; usa a chave do Firecrawl já guardada nas integrações, ou o CLI `firecrawl` se não houver chave):
  python scripts/capture_portal_prints.py --scope nacional_premium --limit 20     # captura os que ainda não têm print
  python scripts/capture_portal_prints.py --domain g1.globo.com                   # um portal
  python scripts/capture_portal_prints.py --pendentes                             # lista o que espera revisão
  python scripts/capture_portal_prints.py --aprovar 12 15 --por apolo             # libera para a vitrine
  python scripts/capture_portal_prints.py --aprovar-todos --por apolo             # libera tudo que está pendente
  python scripts/capture_portal_prints.py --descartar 13

Regras: print fiel (sem editar nem mascarar anúncio), uma captura por portal por vez, pausa entre domínios,
e nada vai à vitrine sem status 'aprovado'. Arquivos em static/images/portais/prints/{portal_id}/{AAAAMMDD}-home.webp.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from aicentralv2 import create_app  # noqa: E402
from aicentralv2.db import get_db  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / 'aicentralv2' / 'static'
PAUSE_SECONDS = 3


def select_portals(args):
    clauses, params = ['active = TRUE'], []
    if args.domain:
        clauses.append('domain = %s'); params.append(args.domain)
    if args.scope:
        clauses.append("to_jsonb(cadu_planner_portals)->>'scope' = %s"); params.append(args.scope)
    if not args.refazer:
        clauses.append("NOT EXISTS (SELECT 1 FROM cadu_planner_portal_prints p WHERE p.portal_id = cadu_planner_portals.id AND p.kind = 'home' AND p.status <> 'descartado')")
    sql = f"SELECT id, domain FROM cadu_planner_portals WHERE {' AND '.join(clauses)} ORDER BY featured_rank ASC NULLS LAST, name ASC LIMIT %s"
    with get_db().cursor() as cur:
        cur.execute(sql, params + [args.limit])
        return cur.fetchall()


def _api_key():
    from aicentralv2.services.integration_credentials import resolve_firecrawl_api_key
    return resolve_firecrawl_api_key() or os.getenv('FIRECRAWL_API_KEY', '').strip()


def _screenshot_url(source):
    """Firecrawl API (the key the app already stores); falls back to the CLI when no key is configured."""
    key = _api_key()
    if key:
        response = requests.post('https://api.firecrawl.dev/v2/scrape', timeout=120,
                                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                                 json={'url': source, 'formats': ['screenshot']})
        response.raise_for_status()
        data = response.json()
        return (data.get('data') or data).get('screenshot')
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'shot.json'
        done = subprocess.run(['firecrawl', 'scrape', source, '--format', 'screenshot', '-o', str(out)], capture_output=True, text=True, timeout=180)
        if done.returncode or not out.exists():
            raise RuntimeError((done.stderr or done.stdout or 'firecrawl falhou').strip()[:200])
        return json.loads(out.read_text()).get('screenshot')


def capture(domain):
    """Screenshot of the portal home, downloaded as an image (max 1440 wide)."""
    source = f'https://{domain}'
    url = _screenshot_url(source)
    if not url:
        raise RuntimeError('sem screenshot na resposta')
    with urllib.request.urlopen(url, timeout=60) as response:
        image = Image.open(io.BytesIO(response.read())).convert('RGB')
    if image.width > 1440:
        image = image.resize((1440, round(image.height * 1440 / image.width)), Image.LANCZOS)
    return source, image


def save(portal_id, source, image):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    relative = f'images/portais/prints/{portal_id}/{stamp}-home.webp'
    target = STATIC / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, 'WEBP', quality=85)
    with get_db().cursor() as cur:
        cur.execute("""INSERT INTO cadu_planner_portal_prints (portal_id, kind, file_path, source_url)
                       VALUES (%s, 'home', %s, %s) ON CONFLICT (portal_id, kind, file_path) DO NOTHING""", (portal_id, relative, source))
    get_db().commit()
    return relative


def review(ids, status, who):
    with get_db().cursor() as cur:
        cur.execute("UPDATE cadu_planner_portal_prints SET status = %s, reviewed_by = %s, reviewed_at = NOW() WHERE id = ANY(%s)", (status, who, ids))
    get_db().commit()
    print(f'{len(ids)} print(s) -> {status}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--domain'); parser.add_argument('--scope', choices=['nacional_premium', 'regional'])
    parser.add_argument('--limit', type=int, default=10); parser.add_argument('--refazer', action='store_true')
    parser.add_argument('--pendentes', action='store_true')
    parser.add_argument('--aprovar', type=int, nargs='+'); parser.add_argument('--descartar', type=int, nargs='+')
    parser.add_argument('--aprovar-todos', action='store_true')
    parser.add_argument('--por', default='')
    args = parser.parse_args()
    if args.aprovar_todos:
        with get_db().cursor() as cur:
            cur.execute("SELECT id FROM cadu_planner_portal_prints WHERE status = 'pendente'")
            pending = [row['id'] for row in cur.fetchall()]
        return review(pending, 'aprovado', args.por) if pending else print('nada pendente')
    if args.aprovar:
        return review(args.aprovar, 'aprovado', args.por)
    if args.descartar:
        return review(args.descartar, 'descartado', args.por)
    if args.pendentes:
        with get_db().cursor() as cur:
            cur.execute("""SELECT p.id, pt.domain, p.file_path, p.captured_at FROM cadu_planner_portal_prints p
                           JOIN cadu_planner_portals pt ON pt.id = p.portal_id WHERE p.status = 'pendente' ORDER BY p.captured_at""")
            for row in cur.fetchall():
                print(f"{row['id']:>5}  {row['domain']:<38} static/{row['file_path']}  {row['captured_at']:%Y-%m-%d}")
        return None
    for row in select_portals(args):
        try:
            source, image = capture(row['domain'])
            print('ok   ', row['domain'], save(row['id'], source, image))
        except Exception as error:  # one broken site must not stop the batch
            print('falha', row['domain'], str(error)[:120])
        time.sleep(PAUSE_SECONDS)
    return None


if __name__ == '__main__':
    with create_app().app_context():
        main()
