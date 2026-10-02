"""Render the real Studio context bar (navbar island + legacy contract) into a static page."""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('aicentralv2/templates'), autoescape=True)
env.globals.update(
    url_for=lambda endpoint, **kw: '/static/' + kw['filename'] if endpoint == 'static' else '/' + endpoint,
    studio_url=lambda endpoint: '/studio/' + endpoint,
    product_url=lambda slug, path='/': f'/{slug}{path}',
    session={'user_name': 'Ana Planejadora', 'user_email': 'ana@agencia.test', 'user_id': 5},
    request=SimpleNamespace(blueprint='studio_product', endpoint='studio_product.home', path='/studio'),
    cadu_nav_credit={'configured': True, 'monthly': 1000, 'available': 640},
    perfil_contato={},
)
bar = env.from_string('{% set mc_page = "criar" %}{% include "cadu_studio/_context_bar.html" %}').render()
styles = ''.join(f'<link rel="stylesheet" href="/static/css/{name}.css">' for name in (
    'cadu-portals', 'cadu-shell-tokens', 'cadu-product-switch', 'cadu-nav-compact', 'cadu-studio-navigation'))
page = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">' + styles +
        '<style>body{margin:0;background:#0b1016;color:#eef2f6;font-family:Arial}</style></head>'
        f'<body class="portal--studio">{bar}<main id="probe" style="padding:24px">Conteúdo</main>'
        '<script src="/static/js/mc-cadu-nav.js" defer></script></body></html>')
out = Path('tests/frontend/.fixtures/studio-navbar')
out.mkdir(parents=True, exist_ok=True)
(out / 'index.html').write_text(page)
