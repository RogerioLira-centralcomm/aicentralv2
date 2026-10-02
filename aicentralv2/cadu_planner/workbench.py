"""Plan Workbench: o estado de co-construção de um plano de mídia.

O plano é dividido em seções. Cada seção tem um estado que diz quem a montou
e se o Cadu ainda pode mexer nela:

- ``vazia``: nada definido.
- ``proposta``: o Cadu deixou uma proposta pendente para o usuário decidir.
- ``aceita``: o usuário aceitou a proposta do Cadu como estava.
- ``editada``: o usuário escreveu ou ajustou a seção à mão.
- ``travada``: o usuário travou a seção; o Cadu não propõe mais nada nela.

Este módulo é puro (sem banco): recebe dicionários e devolve dicionários, para
que as regras de proteção sejam testáveis e iguais nos dois planners.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from werkzeug.exceptions import BadRequest, Conflict

# Ordem de construção: o Cadu propõe a próxima seção ainda aberta nesta ordem.
SECTIONS = (
    ('briefing', 'Briefing', 'O que precisa acontecer, para quem e até quando.'),
    ('objetivo', 'Objetivo e KPIs', 'Awareness, consideração, tráfego ou conversão, e como medir.'),
    ('pracas', 'Praças', 'Onde a oportunidade existe: país, estado, cidade ou raio.'),
    ('audiencias', 'Audiências', 'Quem precisa ser alcançado.'),
    ('canais', 'Canais e papéis', 'Onde comprar e qual o papel de cada canal no plano.'),
    ('formatos', 'Formatos e interativos', 'As peças que cada canal pede.'),
    ('verba', 'Verba e cenários', 'Faixa de investimento, distribuição e alcance provável.'),
    ('criativos', 'Sistema criativo', 'Big idea, mensagens e matriz de peças.'),
)
SECTION_KEYS = tuple(key for key, _label, _hint in SECTIONS)
STATES = ('vazia', 'proposta', 'aceita', 'editada', 'travada')
DONE_STATES = {'aceita', 'editada', 'travada'}
# Seções cujo conteúdo são itens do catálogo (cadu_planner_plan_items).
ITEM_SECTIONS = {'audiencias': ('audiencias',), 'canais': ('canais',), 'formatos': ('formatos', 'interativos')}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _require_section(section):
    if section not in SECTION_KEYS:
        raise BadRequest('Seção do plano desconhecida.')


def derive_state(plan: dict, section: str) -> str:
    """Estado inferido dos dados do plano, para planos criados antes do workbench."""
    briefing = plan.get('briefing') or {}
    kinds = {item.get('kind') for item in plan.get('items') or []}
    filled = {
        'briefing': bool(plan.get('title')) and bool(briefing.get('notes') or plan.get('campaign_name')),
        'objetivo': bool(plan.get('objective')) and bool(briefing.get('kpis')),
        'pracas': bool(briefing.get('geography')),
        'audiencias': 'audiencias' in kinds,
        'canais': 'canais' in kinds,
        'formatos': bool(kinds & {'formatos', 'interativos'}),
        'verba': bool(briefing.get('budget')) and bool(plan.get('allocations')),
        'criativos': False,
    }
    return 'editada' if filled.get(section) else 'vazia'


def section_state(plan: dict, section: str) -> dict:
    """Estado registrado da seção; cai no estado inferido quando não há registro."""
    _require_section(section)
    stored = ((plan.get('workbench') or {}).get('sections') or {}).get(section) or {}
    state = stored.get('state') if stored.get('state') in STATES else derive_state(plan, section)
    return {**stored, 'state': state}


def overview(plan: dict, pending: dict | None = None) -> dict:
    """Seções na ordem de construção, com estado, progresso e próxima seção."""
    pending = pending or {}
    sections = []
    for key, label, hint in SECTIONS:
        state = section_state(plan, key)
        if key in pending and state['state'] not in ('travada',):
            state = {**state, 'state': 'proposta', 'proposal_id': pending[key]}
        sections.append({'key': key, 'label': label, 'hint': hint, **state})
    done = sum(1 for item in sections if item['state'] in DONE_STATES)
    next_open = next((item['key'] for item in sections if item['state'] in ('vazia', 'proposta')), None)
    return {'sections': sections, 'done': done, 'total': len(sections),
            'percent': round(done * 100 / len(sections)), 'next': next_open,
            'revision': int(plan.get('revision') or 0)}


def check_revision(plan: dict, expected_revision) -> None:
    if expected_revision is None:
        return
    try:
        expected = int(expected_revision)
    except (TypeError, ValueError):
        raise BadRequest('Revisão inválida.')
    if expected != int(plan.get('revision') or 0):
        raise Conflict('O plano mudou desde que esta proposta foi feita. Atualize para ver a versão atual.')


def can_propose(plan: dict, section: str) -> bool:
    """O Cadu só propõe em seções que não estão travadas."""
    return section_state(plan, section)['state'] != 'travada'


def apply_proposal(plan: dict, proposal: dict, decision: str, accepted_fields=None, expected_revision=None):
    """Aplica a decisão do usuário sobre uma proposta, sem tocar no banco.

    Devolve ``(workbench, changes)``: o novo workbench e o que precisa ser
    gravado no plano (``changes`` tem chaves por seção, interpretadas pelo
    repositório). Regras:

    - seção travada nunca recebe proposta;
    - proposta feita sobre uma revisão antiga não é aplicada (Conflict);
    - ``partial`` só aplica os campos escolhidos e marca a seção como editada;
    - em seção ``editada`` pelo usuário, aceitar tudo ainda exige decisão
      explícita (é o próprio usuário quem decide), mas o estado continua
      ``editada`` para o Cadu não tratá-la como dele.
    """
    if decision not in ('accepted', 'partial', 'rejected'):
        raise BadRequest('Decisão inválida.')
    section = proposal.get('section')
    _require_section(section)
    if proposal.get('status') != 'pending':
        raise Conflict('Esta proposta já foi decidida.')
    check_revision(plan, expected_revision)
    if int(proposal.get('base_revision') or 0) != int(plan.get('revision') or 0):
        raise Conflict('Esta proposta foi feita sobre uma versão anterior do plano. Peça uma nova ao Cadu.')
    current = section_state(plan, section)
    if current['state'] == 'travada':
        raise Conflict('A seção está travada. Destrave para aceitar propostas.')

    workbench = deepcopy(plan.get('workbench') or {})
    sections = workbench.setdefault('sections', {})
    entry = dict(sections.get(section) or {})
    entry.update(proposal_id=proposal.get('id'), decided_at=_now())
    if decision == 'rejected':
        entry['state'] = current['state'] if current['state'] != 'proposta' else derive_state(plan, section)
        sections[section] = entry
        return workbench, {}

    payload = proposal.get('payload') or {}
    if decision == 'partial':
        fields = [str(field) for field in (accepted_fields or [])]
        if not fields:
            raise BadRequest('Escolha ao menos um campo da proposta para aplicar.')
        unknown = [field for field in fields if field not in payload]
        if unknown:
            raise BadRequest('Campos fora da proposta: ' + ', '.join(unknown) + '.')
        payload = {field: payload[field] for field in fields}
        entry['state'] = 'editada'
    else:
        entry['state'] = 'editada' if current['state'] == 'editada' else 'aceita'
    sections[section] = entry
    return workbench, {section: payload}


def mark_edited(plan: dict, section: str) -> dict:
    """O usuário mexeu na seção à mão: o Cadu passa a tratá-la como do usuário."""
    _require_section(section)
    workbench = deepcopy(plan.get('workbench') or {})
    entry = dict((workbench.setdefault('sections', {})).get(section) or {})
    if entry.get('state') != 'travada':
        entry['state'] = 'editada'
    entry['edited_at'] = _now()
    workbench['sections'][section] = entry
    return workbench


def set_locked(plan: dict, section: str, locked: bool) -> dict:
    _require_section(section)
    workbench = deepcopy(plan.get('workbench') or {})
    entry = dict((workbench.setdefault('sections', {})).get(section) or {})
    if locked:
        entry['state'] = 'travada'
    else:
        entry['state'] = derive_state({**plan, 'workbench': {}}, section)
    entry['locked_at'] = _now() if locked else None
    workbench['sections'][section] = entry
    return workbench
