"""Render the real Criar page (cadu_studio/create.html on the real portal base) into a static file."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template, session  # noqa: E402

from aicentralv2.creative_format_registry import catalog_entries  # noqa: E402
from aicentralv2.creative_media.studio import _studio_reference_masks  # noqa: E402

app = Flask('fixture', root_path=str(ROOT / 'aicentralv2'), template_folder='templates', static_folder='static')
app.secret_key = 'fixture'
app.jinja_env.globals.update(
    studio_url=lambda endpoint, **_: '/studio/' + endpoint,
    product_url=lambda slug, path='/': f'/{slug}{path}',
    cadu_nav_credit={'configured': True, 'monthly': 1000, 'available': 640},
    perfil_contato={},
    skills_enabled=lambda: False,  # mesma chave global do create_app (Skills fora do lançamento)
)

with app.test_request_context('/studio/criar'):
    session.update(user_id=5, user_name='Ana Planejadora', user_email='ana@agencia.test', cliente_id=91)
    html = render_template(
        'cadu_studio/create.html', mc_trocr_csrf='studio-token',
        mc_format_catalog=catalog_entries(), mc_reference_masks=_studio_reference_masks(),
    )
out = ROOT / 'tests/frontend/.fixtures/studio-create'
out.mkdir(parents=True, exist_ok=True)
(out / 'index.html').write_text(html)
