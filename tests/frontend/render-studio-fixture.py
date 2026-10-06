from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, DictLoader


def _atomic_write(target, text):
    # Vários testes de navegador renderizam a mesma fixture em paralelo; troca atômica evita ler arquivo pela metade.
    import os
    tmp = target.with_name(f'.{target.name}.{os.getpid()}.tmp')
    tmp.write_text(text)
    os.replace(tmp, target)
base='''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:20px;background:#f8fafc;font-family:Arial} @media(max-width:600px){body{padding:8px}}</style>{% block styles %}{% endblock %}</head><body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>'''
env=Environment(loader=ChoiceLoader([DictLoader({'base_erp.html':base}),FileSystemLoader('aicentralv2/templates')]),autoescape=True)
def url_for(endpoint, **kwargs):
    if endpoint=='static': return '/static/'+kwargs['filename']
    page=endpoint.split('.')[-1].removeprefix('modelagem_')
    return '/parametros/modelagem-criativos'+('' if page=='criativos' else '/'+page)
env.globals['url_for']=url_for
env.globals['session']={}
env.globals['request']=SimpleNamespace(endpoint='parametros.modelagem_criativos')
env.globals['product_url']=lambda slug, fallback='/': fallback
env.globals['studio_url']=lambda endpoint, **_: '/parametros/modelagem-criativos'
env.globals['skills_enabled']=lambda: False  # chave global do create_app
out=Path('tests/frontend/.fixtures/studio-home');out.mkdir(parents=True,exist_ok=True)
# Produção renderiza cadu_studio/home.html (creative_modeling_routes.modelagem_criativos);
# parametros/modelagem_criativos.html ficou órfão e não carrega os scripts no shell dos portais.
_atomic_write(out/'rendered.html', env.get_template('cadu_studio/home.html').render(mc_page='hub', mc_title='A peça na mesa', mc_trocr_csrf='fixture'))
