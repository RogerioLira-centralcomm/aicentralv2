"""Tipos de ângulo do Radar (prompt 1.6): mídia, conteúdo e inteligência.

Validação da resposta do modelo, catálogo de canais enviado a ele, o que vai para ``score_breakdown`` e o pedido que o
Cadu Chat recebe para produzir uma pauta. O pipeline e o Lab usam as mesmas funções.
"""
from __future__ import annotations

import re
from datetime import date

from ..cadu_family import repository

TYPES = ('midia', 'conteudo', 'inteligencia')
OBJECTIVES = {'awareness', 'consideracao', 'leads', 'vendas', 'trafego'}


def _short(value, limit):
    return ' '.join(str(value or '').split())[:limit]


def channel_catalog():
    """Canais ativos do catálogo, com id curto para o prompt (C1, C2…). Interativos é formato, não canal."""
    rows = [row for row in repository.catalog('canais') if row.get('tipo') != 'interativo']
    return [{'ref': f'C{index + 1}', 'id': row['id'], 'slug': row.get('slug'), 'name': row['name'], 'category': row.get('category') or '',
             'kind': row.get('tipo') or '', 'description': _short(row.get('description'), 160)} for index, row in enumerate(rows)]


def catalog_payload(catalog):
    return [{'id': item['ref'], 'canal': item['name'], 'categoria': item['category'], 'tipo': item['kind'], 'o_que_e': item['description']}
            for item in catalog]


def _period(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key in ('inicio', 'fim'):
        value = str(raw.get(key) or '')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try:
                date.fromisoformat(value)
                out[key] = value
            except ValueError:
                pass
    return out if len(out) == 2 and out['inicio'] <= out['fim'] else {}


def validate(raw, buzz_ids, catalog):
    """Ângulo sem buzz é invenção e sai; canais só do catálogo (os outros são contados e descartados)."""
    by_ref = {item['ref']: item for item in catalog}
    kept = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not item.get('titulo'):
            continue
        ids = [str(value) for value in item.get('buzz') or [] if str(value) in buzz_ids]
        if not ids:
            continue
        kind = item.get('tipo') if item.get('tipo') in TYPES else None
        channels, invalid = [], []
        for entry in item.get('canais') or []:
            ref = str(entry.get('id') or '') if isinstance(entry, dict) else str(entry)
            if ref in by_ref:
                channels.append({'id': by_ref[ref]['id'], 'name': by_ref[ref]['name'],
                                 'formato': _short(entry.get('formato'), 120) if isinstance(entry, dict) else '',
                                 'por_que': _short(entry.get('por_que'), 300) if isinstance(entry, dict) else ''})
            else:
                invalid.append(ref)
        kept.append({
            'tipo': kind, 'por_que_o_tipo': _short(item.get('por_que_o_tipo'), 300), 'titulo': _short(item['titulo'], 160),
            'gancho': _short(item.get('gancho'), 600), 'por_que_agora': _short(item.get('por_que_agora'), 500),
            'janela': _short(item.get('janela'), 120), 'buzz': ids,
            'objetivo': item.get('objetivo') if item.get('objetivo') in OBJECTIVES else None,
            'publico': _short(item.get('publico'), 300), 'pracas': _short(item.get('pracas'), 160), 'periodo': _period(item.get('periodo')),
            'mensagem': _short(item.get('mensagem'), 300), 'canais': channels[:4] if kind in ('midia', 'conteudo') else [], 'canais_invalidos': invalid,
            'assunto': _short(item.get('assunto'), 30),
            'tema': _short(item.get('tema'), 200), 'formatos': [_short(value, 60) for value in item.get('formatos') or [] if value][:5],
            'tom': _short(item.get('tom'), 120), 'impacto': _short(item.get('impacto'), 400), 'observar': _short(item.get('observar'), 400)})
    return kept


def breakdown(angle):
    """Campos do tipo para ``score_breakdown``; ``formats`` e ``channels`` seguem preenchidos para telas antigas."""
    kind = angle.get('tipo')
    data = {'type': kind, 'why_type': angle.get('por_que_o_tipo'), 'subject': angle.get('assunto') or ''}
    if kind == 'midia':
        data.update(objective=angle.get('objetivo'), audience=angle.get('publico'), places=angle.get('pracas'),
                    period=angle.get('periodo') or {}, message=angle.get('mensagem'), media=angle.get('canais') or [],
                    formats=[entry['formato'] for entry in angle.get('canais') or [] if entry.get('formato')][:5],
                    channels=[entry['name'] for entry in angle.get('canais') or []])
    elif kind == 'conteudo':
        data.update(content={'theme': angle.get('tema'), 'message': angle.get('mensagem'), 'formats': angle.get('formatos') or [],
                             'tone': angle.get('tom'), 'channels': [{'id': entry['id'], 'name': entry['name']} for entry in angle.get('canais') or []]}, formats=angle.get('formatos') or [], channels=[])
    elif kind == 'inteligencia':
        data.update(impact=angle.get('impacto'), watch=angle.get('observar'), formats=[], channels=[])
    else:
        data.update(formats=angle.get('formatos') or [], channels=[])
    return data


def chat_prompt(opportunity, *, brand='', focus=''):
    """Pedido para o Cadu Chat produzir a pauta: o Radar não gera conteúdo, só prepara o pedido."""
    detail = opportunity.get('score_breakdown') or {}
    content = detail.get('content') or {}
    sources = [f"- {entry.get('assunto')} ({entry.get('veiculo') or entry.get('domain')}, {entry.get('data')}): {entry.get('url')}"
               for entry in detail.get('buzz') or []]
    parts = [
        f"Produza o conteúdo desta pauta{f' para {brand}' if brand else ''}, vinda do Radar{f' sobre {focus}' if focus else ''}.",
        f"Pauta: {opportunity.get('title')}",
        f"Tese: {opportunity.get('thesis')}" if opportunity.get('thesis') else '',
        f"Tema: {content.get('theme')}" if content.get('theme') else '',
        f"Mensagem: {content.get('message')}" if content.get('message') else '',
        f"Por que agora: {detail.get('why_now')}" if detail.get('why_now') else '',
        f"Formatos: {', '.join(content.get('formats') or detail.get('formats') or [])}" if (content.get('formats') or detail.get('formats')) else '',
        f"Tom: {content.get('tone')}" if content.get('tone') else '',
        'Fontes (use só o que elas sustentam):\n' + '\n'.join(sources) if sources else '',
        'Comece pelo formato principal e proponha os demais em seguida.']
    return '\n'.join(part for part in parts if part)
