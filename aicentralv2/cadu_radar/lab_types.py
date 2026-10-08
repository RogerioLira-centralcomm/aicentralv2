"""Lab dos tipos de ângulo: o prompt atual (1.5) contra o 1.6 (mídia, conteúdo, inteligência) sobre as MESMAS notícias.

Para cada cenário: uma busca de buzz e a conferência dos links (como no produto), depois os ângulos com cada versão.
Nada vai para as tabelas do Radar; as chamadas pagas passam pelo roteador de créditos (``app='Cadu Radar'``).
"""
from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

from . import angle_types, pipeline

TYPES = angle_types.TYPES

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
    return angle_types.channel_catalog()


def angles_v16(runner, ctx, topic, buzz, catalog):
    angles = runner._angles(ctx, topic, buzz, version='1.6', catalog=catalog)
    return angles, runner._step('angles')['tokens']


def validate(raw, buzz, catalog):
    return angle_types.validate(raw, {item['id'] for item in buzz}, catalog)


def run_scenario(client_id, user_id, scenario, catalog):
    tag = uuid4().hex[:8]
    current = LabRunner(client_id, user_id, scenario, f'{tag}-15')
    candidate = LabRunner(client_id, user_id, scenario, f'{tag}-16')
    ctx = current._context()
    topic = current._topic(ctx)
    buzz = current._check(current._buzz(ctx, topic), ctx)
    base_tokens = sum(step['tokens'] for step in current.steps)
    old = current._angles(ctx, topic, buzz, version='1.5') if buzz else []
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
