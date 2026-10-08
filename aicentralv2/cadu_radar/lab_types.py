"""Lab dos tipos de ângulo: o prompt atual (1.5) contra o 1.6 (mídia, conteúdo, inteligência) sobre as MESMAS notícias.

Para cada cenário: uma busca de buzz e a conferência dos links (como no produto), depois os ângulos com cada versão.
Nada vai para as tabelas do Radar; as chamadas pagas passam pelo roteador de créditos (``app='Cadu Radar'``).
"""
from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

from ..cadu_family import repository
from . import pipeline, prompts
from .research import json_loads

TYPES = ('midia', 'conteudo', 'inteligencia')
OBJECTIVES = {'awareness', 'consideracao', 'leads', 'vendas', 'trafego'}


class LabRunner(pipeline.Runner):
    """O Runner do produto sem a linha do run: etapas ficam só na memória."""

    def __init__(self, client_id, user_id, scenario, tag):
        super().__init__(f'lab-types-{tag}', client_id, user_id, scenario['focus'], None, None,
                         {'places': scenario.get('places'), 'recency_days': scenario.get('recency_days', 30)})
        self.scenario = scenario

    def _save_steps(self):
        pass

    def _context(self):
        item = self.scenario
        return {'brand': item.get('brand_name'), 'sector': item.get('sector'), 'project': None, 'site': item.get('site') or '',
                'facts': list(item.get('facts') or [])[:14]}


def channel_catalog():
    """Canais ativos do catálogo, com id curto para o prompt (C1, C2…)."""
    rows = repository.catalog('canais')
    return [{'ref': f'C{index + 1}', 'id': row['id'], 'slug': row.get('slug'), 'name': row['name'], 'category': row.get('category') or ''}
            for index, row in enumerate(rows)]


def angles_v16(runner, ctx, topic, buzz, catalog):
    payload = json.dumps({
        'conceito': topic, 'marca': ctx, 'praca': runner.params['places'] or 'Brasil',
        'buzz': [{key: item[key] for key in ('id', 'assunto', 'por_que', 'data', 'veiculo', 'local')} for item in buzz],
        'catalogo': [{'id': item['ref'], 'canal': item['name'], 'categoria': item['category']} for item in catalog]}, ensure_ascii=False)
    text, tokens = runner._ai('angles', runner.models['angles'], prompts.messages('angles', '1.6', today=runner.today.isoformat(),
                                                                                 payload=payload), max_tokens=8000)
    return validate(json_loads(text).get('angulos') or [], buzz, catalog), tokens


def validate(raw, buzz, catalog):
    """Mesmo filtro do produto (ângulo sem buzz é invenção) e canais só do catálogo; conta o que foi descartado."""
    by_buzz = {item['id'] for item in buzz}
    by_ref = {item['ref']: item for item in catalog}
    kept = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not item.get('titulo'):
            continue
        ids = [str(value) for value in item.get('buzz') or [] if str(value) in by_buzz]
        if not ids:
            continue
        kind = item.get('tipo') if item.get('tipo') in TYPES else None
        channels, invalid = [], []
        for entry in item.get('canais') or []:
            ref = str((entry or {}).get('id') or '') if isinstance(entry, dict) else str(entry)
            if ref in by_ref:
                channels.append({'id': by_ref[ref]['id'], 'name': by_ref[ref]['name'], 'formato': (entry or {}).get('formato') if isinstance(entry, dict) else '',
                                 'por_que': (entry or {}).get('por_que') if isinstance(entry, dict) else ''})
            else:
                invalid.append(ref)
        objective = item.get('objetivo') if item.get('objetivo') in OBJECTIVES else None
        kept.append({**{key: item.get(key) for key in ('titulo', 'gancho', 'por_que_agora', 'janela', 'por_que_o_tipo', 'publico', 'pracas',
                                                        'periodo', 'mensagem', 'tema', 'formatos', 'tom', 'impacto', 'observar')},
                     'tipo': kind, 'objetivo': objective, 'canais': channels, 'canais_invalidos': invalid, 'buzz': ids})
    return kept


def run_scenario(client_id, user_id, scenario, catalog):
    tag = uuid4().hex[:8]
    current = LabRunner(client_id, user_id, scenario, f'{tag}-15')
    candidate = LabRunner(client_id, user_id, scenario, f'{tag}-16')
    ctx = current._context()
    topic = current._topic(ctx)
    buzz = current._check(current._buzz(ctx, topic), ctx)
    base_tokens = sum(step['tokens'] for step in current.steps)
    old = current._angles(ctx, topic, buzz) if buzz else []
    old_tokens = current._step('angles')['tokens'] if buzz else 0
    new, new_tokens = angles_v16(candidate, ctx, topic, buzz, catalog) if buzz else ([], 0)
    return {'scenario': scenario['name'], 'focus': scenario['focus'], 'buzz': buzz, 'tokens_buzz_check': base_tokens - old_tokens,
            'v15': {'angles': old, 'tokens': old_tokens}, 'v16': {'angles': new, 'tokens': new_tokens}}


def summary(result):
    angles = result['v16']['angles']
    kinds = {kind: sum(1 for item in angles if item['tipo'] == kind) for kind in TYPES}
    media = [item for item in angles if item['tipo'] == 'midia']
    return {'cenario': result['scenario'], 'buzz': len(result['buzz']), 'v15_angulos': len(result['v15']['angles']),
            'v16_angulos': len(angles), 'tipos': kinds, 'sem_tipo': sum(1 for item in angles if not item['tipo']),
            'midia_sem_canal': sum(1 for item in media if not item['canais']),
            'canais_invalidos': sum(len(item['canais_invalidos']) for item in angles),
            'midia_sem_objetivo': sum(1 for item in media if not item['objetivo']),
            'tokens': {'busca': result['tokens_buzz_check'], 'v15': result['v15']['tokens'], 'v16': result['v16']['tokens']}}


def report_markdown(results):
    lines = [f'# Lab dos tipos de ângulo ({date.today().isoformat()})', '']
    for result in results:
        info = summary(result)
        lines += [f"## {result['scenario']}: {result['focus']}", '', '```', json.dumps(info, ensure_ascii=False, indent=1), '```', '',
                  '### Buzz', *[f"- {item['assunto']} ({item['veiculo']}, {item['data']})" for item in result['buzz']], '',
                  '### Versão 1.5 (atual)']
        for item in result['v15']['angles']:
            lines += [f"- **{item['titulo']}**: {item['gancho']}", f"  - formatos: {', '.join(item['formatos'])} · canais: {', '.join(item['canais'])}"]
        lines += ['', '### Versão 1.6 (tipos)']
        for item in result['v16']['angles']:
            lines.append(f"- [{item['tipo'] or 'SEM TIPO'}] **{item['titulo']}**: {item['gancho']}")
            lines.append(f"  - por que este tipo: {item.get('por_que_o_tipo')}")
            if item['tipo'] == 'midia':
                period = item.get('periodo') or {}
                lines.append(f"  - objetivo: {item['objetivo']} · público: {item.get('publico')} · praças: {item.get('pracas')} · "
                             f"período: {period.get('inicio')} a {period.get('fim')}")
                lines += [f"  - canal: {entry['name']} ({entry.get('formato')}): {entry.get('por_que')}" for entry in item['canais']]
                if item['canais_invalidos']:
                    lines.append(f"  - canais fora do catálogo descartados: {item['canais_invalidos']}")
            elif item['tipo'] == 'conteudo':
                lines.append(f"  - tema: {item.get('tema')} · formatos: {', '.join(item.get('formatos') or [])} · tom: {item.get('tom')}")
            elif item['tipo'] == 'inteligencia':
                lines.append(f"  - impacto: {item.get('impacto')} · observar: {item.get('observar')}")
        lines.append('')
    return '\n'.join(lines)
