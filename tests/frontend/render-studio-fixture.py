from pathlib import Path
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, DictLoader
base='''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:20px;background:#f8fafc;font-family:Arial} @media(max-width:600px){body{padding:8px}}</style>{% block styles %}{% endblock %}</head><body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>'''
env=Environment(loader=ChoiceLoader([DictLoader({'base_erp.html':base}),FileSystemLoader('aicentralv2/templates')]),autoescape=True)
def url_for(endpoint, **kwargs):
    if endpoint=='static': return '/static/'+kwargs['filename']
    page=endpoint.split('.')[-1].removeprefix('modelagem_')
    return '/parametros/modelagem-criativos'+('' if page=='criativos' else '/'+page)
env.globals['url_for']=url_for
Path('tmp/studio-check/rendered.html').write_text(env.get_template('parametros/modelagem_criativos.html').render())
