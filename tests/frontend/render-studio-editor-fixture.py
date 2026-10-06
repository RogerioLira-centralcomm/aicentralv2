"""Render the real Editar page (cadu_studio/trocr.html on the real portal base) into a static file."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template, session  # noqa: E402


def _atomic_write(target, text):
    # Vários testes de navegador renderizam a mesma fixture em paralelo; troca atômica evita ler arquivo pela metade.
    import os
    tmp = target.with_name(f'.{target.name}.{os.getpid()}.tmp')
    tmp.write_text(text)
    os.replace(tmp, target)

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
_atomic_write(out / 'index.html', html)
