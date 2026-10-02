"""Render the real Editar page (cadu_studio/trocr.html on the real portal base) into a static file."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template, session  # noqa: E402

app = Flask('fixture', root_path=str(ROOT / 'aicentralv2'), template_folder='templates', static_folder='static')
app.secret_key = 'fixture'
app.jinja_env.globals.update(
    studio_url=lambda endpoint, **_: '/studio/' + endpoint,
    product_url=lambda slug, path='/': f'/{slug}{path}',
    static_fingerprint=lambda relative: 'fixture',
    cadu_nav_credit={'configured': True, 'monthly': 1000, 'available': 640},
    perfil_contato={},
    studio_credit={'available': 640, 'monthly_usage_percentage': 36},
)

with app.test_request_context('/studio/editar'):
    session.update(user_id=5, user_name='Ana Planejadora', user_email='ana@agencia.test', cliente_id=91)
    html = render_template('cadu_studio/trocr.html', mc_trocr_csrf='studio-token')
out = ROOT / 'tests/frontend/.fixtures/studio-editor'
out.mkdir(parents=True, exist_ok=True)
(out / 'index.html').write_text(html)
