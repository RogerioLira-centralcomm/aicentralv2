"""Extensões internas do editor de vídeo, declaradas por manifesto JSON nesta pasta.

Cada ``<id>.json`` descreve nome, grupo, parâmetros (o editor monta o formulário) e ``handler``,
o nome de uma função deste pacote. Só código revisado no repositório é carregado: o manifesto
não aceita caminho nem módulo arbitrário. O handler recebe o contexto do projeto e devolve
``(comandos, resumo)``; quem aplica e valida os comandos é a Editor API.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from . import captions, titles

HANDLERS = {
    'titles.add_title': titles.add_title,
    'captions.auto_captions': captions.auto_captions,
}
_PARAM_TYPES = {'text', 'number', 'select', 'color', 'media'}


@lru_cache(maxsize=1)
def _manifests():
    items = {}
    for path in sorted(Path(__file__).parent.glob('*.json')):
        manifest = json.loads(path.read_text())
        ident = manifest.get('id')
        if not re.fullmatch(r'[a-z0-9-]{3,40}', str(ident or '')) or ident != path.stem:
            raise ValueError(f'Manifesto inválido: {path.name}')
        if manifest.get('handler') not in HANDLERS:
            raise ValueError(f'Handler desconhecido em {path.name}')
        for param in manifest.get('params', []):
            if param.get('type') not in _PARAM_TYPES or not re.fullmatch(r'[a-z_]{1,40}', str(param.get('key') or '')):
                raise ValueError(f'Parâmetro inválido em {path.name}')
        items[ident] = manifest
    return items


def catalog():
    return [{key: manifest[key] for key in ('id', 'name', 'description', 'group', 'params')} for manifest in _manifests().values()]


def run(ident, context, params):
    manifest = _manifests().get(ident)
    if not manifest:
        raise ValueError('Extensão não encontrada.')
    clean = {}
    for param in manifest.get('params', []):
        value = params.get(param['key'], param.get('default'))
        if param['type'] == 'number':
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(f'{param["label"]}: informe um número.')
            value = max(param.get('min', value), min(param.get('max', value), value))
        elif param['type'] == 'select' and value not in {option['value'] for option in param.get('options', [])}:
            raise ValueError(f'{param["label"]}: opção inválida.')
        else:
            value = str(value or '')[:500]
        clean[param['key']] = value
    try:
        clean['playhead_seconds'] = max(0.0, float(params.get('playhead_seconds') or 0))
    except (TypeError, ValueError):
        clean['playhead_seconds'] = 0.0
    return HANDLERS[manifest['handler']](context, clean)
