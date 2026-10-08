"""Plano final do Cadu Planner: um documento gerado por IA a partir do plano.

Independente do smart_planner (só a referência de método): payload, prompt e
validação próprios, pensados nos dados que o Cadu Planner coleta.

- ``build_payload``: contexto compacto do plano, separando o que é dado
  confirmado do que é lacuna.
- ``validate``: transforma a resposta do modelo no documento final, removendo
  números sem lastro, canais fora do plano, metas inventadas e dado de mercado
  sem fonte. Percentuais e R$ do mix vêm sempre das alocações.
- Versões: toda geração, edição ou revisão grava uma versão nova; nada é
  sobrescrito. O documento fica desatualizado quando o payload do plano muda.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import unicodedata
from uuid import uuid4

from werkzeug.exceptions import BadRequest, Conflict, NotFound

PROMPT_PATH = Path(__file__).with_name('final_plan_prompt.md')
PROMPT_VERSION = 'final-plan-v1'
MAX_PAYLOAD_CHARS = 24_000
MAX_LIST = 30
MAX_TEXT = 600
MAX_SECTION_BODY = 12_000
OUTPUT_TOKENS = 6_000          # teto de saída usado na estimativa (inclui raciocínio)
PRICE_NOTE = 'Valores sujeitos a cotação e à disponibilidade de inventário.'

SECTIONS = (
    ('resumo', 'Folha-resumo'),
    ('visao', 'Visão e objetivo'),
    ('kpis', 'KPIs'),
    ('praca', 'Praças'),
    ('audiencia', 'Audiência'),
    ('mix', 'Mix de canais'),
    ('criativo', 'Direção criativa'),
    ('fases', 'Fases do voo'),
    ('premissas', 'Premissas'),
    ('proximos_passos', 'Próximos passos'),
    ('para_alinharmos', 'Para alinharmos'),
)
SECTION_KEYS = tuple(key for key, _ in SECTIONS)
SECTION_TITLES = dict(SECTIONS)
OBJECTIVE_LABELS = {'awareness': 'Awareness', 'consideracao': 'Consideração', 'leads': 'Leads',
                    'vendas': 'Vendas', 'trafego': 'Tráfego', 'outro': 'Outro'}
# Plataformas conhecidas: citadas no texto sem estar no plano, a frase sai.
KNOWN_CHANNELS = ('meta', 'facebook', 'instagram', 'google', 'youtube', 'tiktok', 'linkedin', 'spotify',
                  'kwai', 'pinterest', 'twitter', 'twitch', 'netflix', 'prime video', 'globoplay', 'waze',
                  'uber', 'ifood', 'deezer', 'snapchat', 'reddit', 'threads', 'whatsapp')
_CONTACT = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+|\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b')
_NUMBER = re.compile(r'(?:r\$\s*)?\d[\d.,]*\s*(?:%|mil\b|milh\w+|mi\b|bi\b|k\b)?', re.I)


# ---------------------------------------------------------------- payload

def _fold(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return ' '.join(text.lower().split())


def _short(value, limit=MAX_TEXT):
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit - 1].rsplit(' ', 1)[0] + '…'


def _compact(value, depth=0):
    """Bound any loose workbench value (lists, dicts, text) before it reaches the model."""
    if isinstance(value, Mapping):
        return {str(k)[:60]: _compact(v, depth + 1) for k, v in list(value.items())[:MAX_LIST]
                if v not in (None, '', [], {})} if depth < 4 else _short(json.dumps(value, ensure_ascii=False, default=str))
    if isinstance(value, (list, tuple)):
        return [_compact(v, depth + 1) for v in list(value)[:MAX_LIST]]
    if isinstance(value, (int, float, Decimal)):
        return float(value) if isinstance(value, Decimal) else value
    return _short(value)


def _section_value(plan, section):
    return (((plan.get('workbench') or {}).get('sections') or {}).get(section) or {}).get('value') or {}


def _channel_roles(plan):
    """Workbench roles may arrive as {id: role}, [{resource_id, role}] or [{name, papel}]."""
    raw = _section_value(plan, 'canais').get('roles')
    roles = {}
    if isinstance(raw, Mapping):
        roles = {str(k): str(v.get('role') or v.get('papel') or '') if isinstance(v, Mapping) else str(v)
                 for k, v in raw.items()}
    elif isinstance(raw, list):
        for row in raw:
            if isinstance(row, Mapping):
                key = str(row.get('resource_id') or row.get('id') or row.get('canal_id') or row.get('name') or '')
                if key:
                    roles[key] = str(row.get('role') or row.get('papel') or '')
    return {k: _short(v, 200) for k, v in roles.items() if v}


def allocation_rows(plan):
    """Channel rows with money and share exactly as the allocations say (no rounding tricks)."""
    allocations = {str(row.get('resource_id')): row for row in plan.get('allocations') or []}
    channels = [item for item in plan.get('items') or [] if item.get('kind') == 'canais']
    total = sum(Decimal(str(allocations.get(str(item['resource_id']), {}).get('investment') or 0)) for item in channels)
    roles = _channel_roles(plan)
    rows = []
    for item in channels:
        snapshot = item.get('snapshot') or {}
        rid = str(item['resource_id'])
        allocation = allocations.get(rid) or {}
        investment = Decimal(str(allocation.get('investment') or 0))
        weight = Decimal(str(allocation.get('weight') or 0))
        share = (investment * 100 / total) if total else weight
        rows.append({
            'canal_id': rid, 'canal': snapshot.get('name') or rid, 'categoria': snapshot.get('category') or '',
            'investimento': float(investment) if investment else None,
            'percentual': round(float(share), 1) if share else None,
            'voo': allocation.get('flight') or '', 'notas': _short(allocation.get('notes'), 300),
            'papel': roles.get(rid) or roles.get(str(snapshot.get('name') or '')) or '',
        })
    return rows, (float(total) if total else None)


def build_payload(plan: Mapping, *, story=None, pending=None) -> dict:
    """Context the model sees: `confirmado` holds plan facts, `lacunas` what is missing."""
    from .balance import parse_budget
    briefing = plan.get('briefing') or {}
    rows, allocated = allocation_rows(plan)
    items = plan.get('items') or []

    def names(kinds, extra=()):
        out = []
        for item in items:
            if item.get('kind') in kinds:
                snap = item.get('snapshot') or {}
                entry = {'nome': snap.get('name') or str(item.get('resource_id'))}
                for key in ('category',) + tuple(extra):
                    if snap.get(key):
                        entry[key] = _short(snap[key], 160)
                out.append(entry)
        return out[:MAX_LIST]

    creative = {key: _compact(value) for key, value in _section_value(plan, 'criativos').items()
                if key in ('big_idea', 'messages', 'matrix') and value not in (None, '', [], {})}
    confirmed = {
        'plano': {'titulo': plan.get('title'), 'anunciante': plan.get('advertiser_name'),
                  'campanha': plan.get('campaign_name'),
                  'objetivo': OBJECTIVE_LABELS.get(plan.get('objective'), plan.get('objective'))},
        'briefing': {key: briefing.get(key) for key in ('budget', 'period', 'geography', 'kpis', 'notes')},
        'verba': {'informada': parse_budget(briefing.get('budget')) if briefing.get('budget') else None,
                  'alocada_nos_canais': allocated},
        'canais': rows[:MAX_LIST],
        'audiencias': names({'audiencias'}, ('audience', 'platform')),
        'formatos': names({'formatos', 'interativos'}, ('platform',)),
        'portais': names({'portais'}, ('domain',)),
        'places': names({'places'}, ('city',)),
        'cenarios_de_verba': _compact(_section_value(plan, 'verba').get('scenarios')),
        'sistema_criativo': creative or None,
        'historia': None,
    }
    if story:
        confirmed['historia'] = {'angulo': _short(story.get('angle'), 200), 'por_que_agora': _short(story.get('why_now')),
                                 'janela': _short(story.get('window'), 200),
                                 'noticias': [{'titulo': _short(n.get('title'), 200), 'veiculo': n.get('source'),
                                               'data': n.get('date'), 'url': n.get('url')}
                                              for n in story.get('buzz') or []][:5]}
    confirmed['plano'] = {k: v for k, v in confirmed['plano'].items() if v}
    confirmed['briefing'] = {k: _short(v, 2000) for k, v in confirmed['briefing'].items() if v}
    confirmed = {k: v for k, v in confirmed.items() if v not in (None, '', [], {})}
    gaps = []
    checks = (('objetivo', plan.get('objective')), ('período', briefing.get('period')),
              ('praça', briefing.get('geography')), ('KPIs', briefing.get('kpis')),
              ('verba', briefing.get('budget') or allocated), ('canais', rows),
              ('audiências', confirmed.get('audiencias')), ('formatos', confirmed.get('formatos')))
    gaps += [f'{label} não definido no plano' for label, value in checks if not value]
    gaps += [f'canal {row["canal"]} sem verba registrada' for row in rows if not row['investimento'] and not row['percentual']]
    payload = {'confirmado': confirmed, 'lacunas': gaps,
               'pendencias': [_short(p, 200) for p in pending or []][:8]}
    text = json.dumps(payload, ensure_ascii=False, default=str)
    while len(text) > MAX_PAYLOAD_CHARS:   # shrink the longest lists first; facts above stay
        longest = max((k for k in ('portais', 'places', 'audiencias', 'formatos') if confirmed.get(k)),
                      key=lambda k: len(confirmed[k]), default=None)
        if not longest or len(confirmed[longest]) <= 3:
            confirmed.get('briefing', {})['notes'] = _short(confirmed.get('briefing', {}).get('notes'), 800)
            break
        confirmed[longest] = confirmed[longest][:len(confirmed[longest]) // 2]
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return payload


def payload_hash(payload: Mapping) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def build_prompt(payload: Mapping, instructions: str = '', previous: Mapping | None = None) -> str:
    prompt = PROMPT_PATH.read_text(encoding='utf-8')
    prompt += '\n\nCONTEXTO:\n' + json.dumps(payload, ensure_ascii=False, default=str)
    if previous:
        prompt += ('\n\nVERSÃO ATUAL DO DOCUMENTO (mantenha o que não for pedido para mudar):\n'
                   + to_markdown(previous)[:12_000])
    if instructions:
        prompt += ('\n\nAJUSTES PEDIDOS PELO USUÁRIO (aplique sem quebrar as regras acima):\n'
                   + _short(instructions, 2000))
    return prompt


# ---------------------------------------------------------------- validation

def _num_key(token):
    digits = re.sub(r'[^\d]', '', token.split(',')[0] if re.search(r',\d{1,2}\b', token) else token)
    return digits.lstrip('0') or '0'


def allowed_numbers(payload: Mapping) -> set[str]:
    """Every number that appears in the plan's context (plus computed shares/totals)."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    found = {_num_key(m.group(0)) for m in re.finditer(r'\d[\d.,]*', text)}
    for value in re.findall(r'\d+\.\d+', text):     # 12.5 → also allow 12,5 / 12 / 13
        whole, _, frac = value.partition('.')
        found |= {whole, str(round(float(value)))}
    from .balance import parse_budget
    for match in _NUMBER.finditer(text):
        amount = parse_budget(match.group(0)) if re.search(r'mil|mi|k|r\$', match.group(0), re.I) else None
        if amount:
            found.add(str(amount))
    return found


def _bad_numbers(sentence, allowed):
    bad = []
    for match in _NUMBER.finditer(sentence):
        token = match.group(0).strip()
        key = _num_key(token)
        money_or_share = bool(re.search(r'%|r\$|mil|mi\b|milh|bi\b|k\b', token, re.I))
        if not money_or_share and (len(key) <= 2 or (len(key) == 4 and 1990 <= int(key) <= 2100)):
            continue  # ordinals, counts and years
        from .balance import parse_budget
        scaled = parse_budget(token) if re.search(r'mil|mi|k|r\$', token, re.I) else None
        if key not in allowed and str(scaled or '') not in allowed:
            bad.append(token)
    return bad


def _foreign_channels(sentence, plan_names):
    folded = _fold(sentence)
    return [name for name in KNOWN_CHANNELS
            if re.search(r'\b' + re.escape(name) + r'\b', folded) and not any(name in n for n in plan_names)]


def clean_text(value, allowed, plan_names, warnings, where, limit=MAX_TEXT * 3):
    """Drop sentences with unsupported numbers or channels outside the plan; strip contacts."""
    text = _CONTACT.sub('', ' '.join(str(value or '').split()))
    kept = []
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if not sentence:
            continue
        numbers, channels = _bad_numbers(sentence, allowed), _foreign_channels(sentence, plan_names)
        if numbers or channels:
            warnings.append({'section': where, 'removed': _short(sentence, 200),
                             'reason': ('número sem base no plano: ' + ', '.join(numbers)) if numbers
                             else ('canal fora do plano: ' + ', '.join(channels))})
            continue
        kept.append(sentence)
    return _short(' '.join(kept), limit)


def _bullets(values):
    return '\n'.join(f'- {v}' for v in values if v)


def _money(value):
    if not value:
        return ''
    return 'R$ ' + f'{value:,.0f}'.replace(',', '.')


def validate(raw: Mapping, payload: Mapping) -> tuple[dict, list]:
    """Model JSON → document sections. Deterministic; never trusts numbers it cannot trace."""
    if not isinstance(raw, Mapping):
        raise BadRequest('O Cadu não devolveu um plano utilizável. Tente novamente.')
    confirmed = payload.get('confirmado') or {}
    channels = confirmed.get('canais') or []
    plan_names = {_fold(row['canal']) for row in channels} | {_fold(row.get('categoria')) for row in channels}
    plan_names |= {_fold(i.get('nome')) for k in ('audiencias', 'formatos', 'portais', 'places') for i in confirmed.get(k) or []}
    allowed, warnings = allowed_numbers(payload), []
    text = lambda key, where=None: clean_text(raw.get(key), allowed, plan_names, warnings, where or key)
    as_list = lambda key: [item for item in (raw.get(key) or []) if item] if isinstance(raw.get(key), list) else []

    pending = list(payload.get('pendencias') or [])
    sections = {}

    market = raw.get('dado_de_mercado') if isinstance(raw.get('dado_de_mercado'), Mapping) else {}
    news = {n.get('url'): n for n in (confirmed.get('historia') or {}).get('noticias') or [] if n.get('url')}
    market_line = ''
    if market.get('texto'):
        source = news.get(str(market.get('fonte_url') or '').strip())
        if source:
            market_line = f"{_short(market['texto'], 400)} (Fonte: [{source.get('veiculo') or source.get('titulo')}]({source['url']}))"
        else:
            warnings.append({'section': 'resumo', 'removed': _short(market['texto'], 200), 'reason': 'dado de mercado sem fonte do plano'})
    thesis = text('tese', 'resumo')
    summary = [f'**Tese.** {thesis}' if thesis else '',
               f"**Estratégia.** {text('estrategia', 'resumo')}" if raw.get('estrategia') else '',
               f"**Criativo no canal.** {text('criativo_no_canal', 'resumo')}" if raw.get('criativo_no_canal') else '',
               f'**Dado de mercado.** {market_line}' if market_line else '',
               f"**Por que este plano.** {text('defesa', 'resumo')}" if raw.get('defesa') else '']
    sections['resumo'] = '\n\n'.join(line for line in summary if line and not line.endswith('** '))

    sections['visao'] = text('visao')
    kpi_lines = []
    for row in as_list('kpis'):
        if not isinstance(row, Mapping) or not row.get('kpi'):
            continue
        kpi = clean_text(row.get('kpi'), allowed, plan_names, warnings, 'kpis', 200)
        meta = str(row.get('meta') or '').strip()
        if meta and _bad_numbers(meta, allowed):
            warnings.append({'section': 'kpis', 'removed': meta, 'reason': 'meta sem base no briefing'})
            meta = ''
        if kpi and not meta:
            pending.append(f'Definir a meta de {kpi}.')
        base = clean_text(row.get('base'), allowed, plan_names, warnings, 'kpis', 200)
        kpi_lines.append(f"**{kpi}**" + (f' — meta: {meta}' if meta else ' — meta a definir') + (f' ({base})' if base else ''))
    sections['kpis'] = _bullets(kpi_lines)
    sections['praca'] = text('praca')
    sections['audiencia'] = text('audiencia')

    by_id = {}
    for row in as_list('mix'):
        if isinstance(row, Mapping):
            rid = str(row.get('canal_id') or '')
            if rid in {c['canal_id'] for c in channels}:
                by_id[rid] = row
            else:
                warnings.append({'section': 'mix', 'removed': _short(json.dumps(row, ensure_ascii=False), 200), 'reason': 'canal fora do plano'})
    mix_rows = []
    for channel in channels:
        llm = by_id.get(channel['canal_id']) or {}
        mix_rows.append({
            'canal': channel['canal'],
            'percentual': channel.get('percentual'),
            'investimento': channel.get('investimento'),
            'papel': channel.get('papel') or clean_text(llm.get('papel'), allowed, plan_names, warnings, 'mix', 200),
            'justificativa': clean_text(llm.get('justificativa'), allowed, plan_names, warnings, 'mix', 500),
        })
    sections['mix'] = ''
    sections['criativo'] = text('direcao_criativa', 'criativo')
    phases = []
    for row in as_list('fases'):
        if isinstance(row, Mapping) and row.get('fase'):
            line = clean_text(f"{row.get('fase')}" + (f" ({row['quando']})" if row.get('quando') else '')
                              + (f": {row['foco']}" if row.get('foco') else ''), allowed, plan_names, warnings, 'fases', 400)
            if line:
                phases.append(line)
    sections['fases'] = _bullets(phases)
    for key in ('premissas', 'proximos_passos'):
        sections[key] = _bullets(clean_text(v, allowed, plan_names, warnings, key, 300) for v in as_list(key))
    for item in as_list('para_alinharmos'):
        item = clean_text(item, allowed, plan_names, warnings, 'para_alinharmos', 300)
        if item and _fold(item) not in {_fold(p) for p in pending}:
            pending.append(item)
    pending += [f'Confirmar: {gap}.' for gap in payload.get('lacunas') or []
                if not any(_fold(gap.split(' ')[0]) in _fold(p) for p in pending)]
    sections['para_alinharmos'] = _bullets(dict.fromkeys(pending))
    if not thesis:
        raise BadRequest('O Cadu não devolveu uma tese para o plano. Tente novamente.')
    document = {'sections': [{'key': key, 'title': SECTION_TITLES[key], 'body': sections.get(key) or '',
                              **({'rows': mix_rows} if key == 'mix' else {})} for key in SECTION_KEYS],
                'note': PRICE_NOTE}
    return document, warnings


def parse_json(content) -> dict:
    raw = str(content or '').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', raw, flags=re.S | re.I)
    try:
        parsed = json.loads(fenced.group(1) if fenced else raw)
    except (TypeError, ValueError):
        raise BadRequest('O Cadu não devolveu um plano utilizável. Tente novamente.')
    if not isinstance(parsed, dict):
        raise BadRequest('O Cadu não devolveu um plano utilizável. Tente novamente.')
    return parsed


def mix_table(rows) -> str:
    if not rows:
        return ''
    lines = ['| Canal | % | R$ | Papel | Justificativa |', '|---|---|---|---|---|']
    for row in rows:
        pct = f"{row['percentual']:.1f}".replace('.', ',').replace(',0', '') + '%' if row.get('percentual') else 'a definir'
        cells = [row.get('canal'), pct, _money(row.get('investimento')) or 'a definir',
                 row.get('papel') or '', row.get('justificativa') or '']
        lines.append('| ' + ' | '.join(str(c or '').replace('|', '/') for c in cells) + ' |')
    return '\n'.join(lines)


def to_markdown(document: Mapping, title: str = '') -> str:
    """Clean markdown for the chat, the project knowledge and copy/paste."""
    out = [f'# Plano final — {title}' if title else '# Plano final']
    for section in document.get('sections') or []:
        body = '\n\n'.join(part for part in (mix_table(section.get('rows')) if section.get('key') == 'mix' else '',
                                             section.get('body') or '') if part)
        if body:
            out.append(f"## {section.get('title')}\n\n{body}")
    out.append(f"_{document.get('note') or PRICE_NOTE}_")
    return '\n\n'.join(out)


def merge_edited(new_doc: Mapping, previous: Mapping | None, edited: list, overwrite: bool) -> tuple[dict, list]:
    """Regeneration keeps sections the user edited unless they confirmed overwriting."""
    if overwrite or not previous or not edited:
        return dict(new_doc), []
    old = {s['key']: s for s in previous.get('sections') or []}
    sections = [old[s['key']] if s['key'] in edited and s['key'] in old else s for s in new_doc.get('sections') or []]
    return {**new_doc, 'sections': sections}, [k for k in edited if k in old]


def apply_section_edit(document: Mapping, section: str, body: str) -> dict:
    if section not in SECTION_KEYS:
        raise BadRequest('Seção do plano final desconhecida.')
    body = str(body or '').strip()
    if len(body) > MAX_SECTION_BODY:
        raise BadRequest(f'O texto da seção passa de {MAX_SECTION_BODY:,} caracteres.'.replace(',', '.'))
    return {**document, 'sections': [{**s, 'body': body} if s['key'] == section else s
                                     for s in document.get('sections') or []]}


def public_projection(row: Mapping | None) -> dict | None:
    """What a shared link shows: the document text only (no ids, costs, credits, warnings or authors)."""
    if not row or not row.get('document'):
        return None
    document = row['document']
    sections = []
    for s in document.get('sections') or []:
        item = {'key': s.get('key'), 'title': s.get('title'), 'body': s.get('body') or ''}
        if s.get('rows'):
            item['rows'] = [{k: r.get(k) for k in ('canal', 'percentual', 'investimento', 'papel', 'justificativa')}
                            for r in s['rows']]
        if item['body'] or item.get('rows'):
            sections.append(item)
    return {'title': row.get('plan_title') or '', 'advertiser_name': row.get('advertiser_name') or '',
            'version': row.get('version'), 'updated_at': row.get('created_at'), 'sections': sections,
            'note': document.get('note') or PRICE_NOTE}


# ---------------------------------------------------------------- persistence

def available() -> bool:
    from ..cadu_family import repository
    rows = repository.rows("""SELECT to_regclass('public.cadu_planner_final_plans') IS NOT NULL
                                 AND to_regclass('public.cadu_planner_final_plan_shares') IS NOT NULL AS available""")
    return bool(rows and rows[0]['available'])


def _require_available():
    if not available():
        raise BadRequest('Aplique a migration do plano final do Planner antes de usar este recurso.')


def _latest(plan_id):
    from ..cadu_family import repository
    rows = repository.rows('''SELECT id, plan_id, version, plan_revision, source_hash, document, edited_sections,
                                     origin, warnings, charged_tokens, project_source_id, created_at
                                FROM cadu_planner_final_plans WHERE plan_id = %s
                            ORDER BY version DESC LIMIT 1''', (str(plan_id),))
    return rows[0] if rows else None


def _share(plan_id):
    from ..cadu_family import repository
    rows = repository.rows('SELECT share_token, share_enabled FROM cadu_planner_final_plan_shares WHERE plan_id = %s', (str(plan_id),))
    return rows[0] if rows else {'share_token': None, 'share_enabled': False}


def _context(client_id, actor_id, plan_id):
    from . import plans
    plan = plans.get_plan(client_id, actor_id, plan_id)
    payload = build_payload(plan, story=plans._public_story(plan['id']), pending=plans._public_pending(plan['id']))
    return plan, payload


def describe(plan, payload, latest, share) -> dict:
    """State shown in the Planner and returned to the chat/MCP."""
    result = {'available': True, 'exists': bool(latest), 'share_enabled': bool(share.get('share_enabled')),
              'share_token': share.get('share_token') if share.get('share_enabled') else None}
    if latest:
        result.update({
            'version': latest['version'], 'created_at': latest['created_at'], 'origin': latest['origin'],
            'document': latest['document'], 'edited_sections': latest.get('edited_sections') or [],
            'warnings': latest.get('warnings') or [], 'project_source_id': latest.get('project_source_id'),
            'stale': latest['source_hash'] != payload_hash(payload),
            'generated_at_revision': latest.get('plan_revision'), 'plan_revision': int(plan.get('revision') or 0),
            'markdown': to_markdown(latest['document'], plan.get('title') or ''),
        })
    return result


def get_state(client_id, actor_id, plan_id) -> dict:
    if not available():
        return {'available': False, 'exists': False}
    plan, payload = _context(client_id, actor_id, plan_id)
    return describe(plan, payload, _latest(plan['id']), _share(plan['id']))


def estimate(client_id, actor_id, plan_id) -> int:
    from .revisions import TEXT_AGENT_MARGIN_MULTIPLIER
    _plan, payload = _context(client_id, actor_id, plan_id)
    source_chars = len(PROMPT_PATH.read_text(encoding='utf-8')) + len(json.dumps(payload, ensure_ascii=False, default=str))
    # One call with one possible JSON retry: two inputs, one generous output ceiling.
    tokens = 2 * ((source_chars + 3) // 4) + OUTPUT_TOKENS + 800
    return tokens * TEXT_AGENT_MARGIN_MULTIPLIER


def _insert_version(plan, *, payload, document, edited, origin, warnings, charged, actor_id, instructions=None,
                    expected_version=None):
    from ..db import get_db
    from psycopg.types.json import Json
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'planner-final:{plan["id"]}',))
        cur.execute('SELECT COALESCE(MAX(version), 0) AS v FROM cadu_planner_final_plans WHERE plan_id = %s', (str(plan['id']),))
        current = int(cur.fetchone()['v'])
        if expected_version is not None and int(expected_version) != current:
            raise Conflict('O plano final mudou desde que você abriu. Atualize para ver a versão atual.')
        cur.execute('''INSERT INTO cadu_planner_final_plans
                         (id, plan_id, client_id, version, plan_revision, source_hash, document, edited_sections,
                          origin, warnings, instructions, charged_tokens, prompt_version, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (str(uuid4()), str(plan['id']), plan.get('client_id') or plan['_client_id'], current + 1,
                     int(plan.get('revision') or 0), payload_hash(payload), Json(document), Json(sorted(set(edited))),
                     origin, Json(warnings[:40]), instructions or None, int(charged), PROMPT_VERSION, actor_id))


def _charge(credits, actor, run_id, attempt, response, plan_id):
    from .revisions import TEXT_AGENT_MARGIN_MULTIPLIER
    charge = credits.charge_provider(
        actor=actor, idempotency_key=f'planner-final-plan:{run_id}:{attempt}', app='Cadu Planner', stage='final_plan',
        provider_result={'usage': dict(response.get('usage') or {}), 'model': str(response.get('model') or 'planner-final-plan'),
                         'actual_cost_usd': response.get('cost_usd') or 0},
        metadata={'run_id': run_id, 'attempt': attempt, 'scope': 'final_plan', 'target_id': str(plan_id),
                  'billing_class': 'text_agent'},
        margin_multiplier=TEXT_AGENT_MARGIN_MULTIPLIER)
    return int((charge or {}).get('tokens_cobrados') or 0)


def generate(client_id, actor_id, plan_id, *, overwrite_edited=False, instructions='', provider=None, credits=None) -> dict:
    """Generate (or revise, with instructions) a new version. Charged per real provider response."""
    _require_available()
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    plan, payload = _context(client_id, actor_id, plan_id)
    if not [i for i in plan.get('items') or [] if i.get('kind') == 'canais'] and not (plan.get('briefing') or {}).get('notes'):
        raise BadRequest('Adicione ao menos um canal ou escreva o briefing antes de gerar o plano final.')
    previous = _latest(plan['id'])
    credits = credits or CaduCreditConnector()
    actor = CreditActor.from_values(client_id, actor_id)
    credits.authorize(actor, estimate(client_id, actor_id, plan_id))
    if provider is None:
        from ..training_studio.providers import TextProvider
        provider = TextProvider()
    prompt = build_prompt(payload, instructions, previous['document'] if previous and instructions else None)
    run_id, charged, document, warnings = str(uuid4()), 0, None, []
    for attempt in (1, 2):
        response = provider.complete([
            {'role': 'system', 'content': 'Você escreve planos de mídia fiéis aos dados fornecidos. Responda só JSON válido.'},
            {'role': 'user', 'content': prompt},
        ], max_tokens=None, temperature=0.2, response_format={'type': 'json_object'})
        charged += _charge(credits, actor, run_id, attempt, response, plan['id'])
        try:
            document, warnings = validate(parse_json(response.get('content')), payload)
            break
        except BadRequest:
            if attempt == 2:
                raise
    edited = list((previous or {}).get('edited_sections') or [])
    document, kept = merge_edited(document, (previous or {}).get('document'), edited, overwrite_edited)
    _insert_version({**plan, '_client_id': client_id}, payload=payload, document=document, edited=kept,
                    origin='revised' if instructions else 'generated', warnings=warnings, charged=charged,
                    actor_id=actor_id, instructions=_short(instructions, 2000) if instructions else None)
    state = get_state(client_id, actor_id, plan_id)
    state['charged_tokens'] = charged
    state['kept_edited_sections'] = kept
    return state


def update_section(client_id, actor_id, plan_id, section, body, *, expected_version=None) -> dict:
    """User edit (Planner, chat or MCP): always a new version; the section becomes the user's."""
    _require_available()
    plan, payload = _context(client_id, actor_id, plan_id)
    latest = _latest(plan['id'])
    if not latest:
        raise NotFound('Gere o plano final antes de editar.')
    document = apply_section_edit(latest['document'], section, body)
    edited = list(latest.get('edited_sections') or []) + [section]
    # The edit does not refresh the plan data: keep the hash the text was generated from.
    from ..db import get_db
    from psycopg.types.json import Json
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (f'planner-final:{plan["id"]}',))
        cur.execute('SELECT COALESCE(MAX(version), 0) AS v FROM cadu_planner_final_plans WHERE plan_id = %s', (str(plan['id']),))
        current = int(cur.fetchone()['v'])
        if expected_version not in (None, '') and int(expected_version) != current:
            raise Conflict('O plano final mudou desde que você abriu. Atualize para ver a versão atual.')
        cur.execute('''INSERT INTO cadu_planner_final_plans
                         (id, plan_id, client_id, version, plan_revision, source_hash, document, edited_sections,
                          origin, warnings, charged_tokens, prompt_version, created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'edited','[]'::jsonb,0,%s,%s)''',
                    (str(uuid4()), str(plan['id']), client_id, current + 1, latest.get('plan_revision') or 0,
                     latest['source_hash'], Json(document), Json(sorted(set(edited))), PROMPT_VERSION, actor_id))
    return get_state(client_id, actor_id, plan_id)


def set_share(client_id, actor_id, plan_id, enabled) -> dict:
    """Open link (no login) to the current version; the token survives disable/enable."""
    _require_available()
    from . import plans
    from ..db import get_db
    plan = plans.get_plan(client_id, actor_id, plan_id)
    if enabled and not _latest(plan['id']):
        raise BadRequest('Gere o plano final antes de compartilhar.')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cadu_planner_final_plan_shares (plan_id, share_token, share_enabled, updated_by)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (plan_id) DO UPDATE SET share_enabled = EXCLUDED.share_enabled,
                              updated_by = EXCLUDED.updated_by, updated_at = NOW()''',
                    (str(plan['id']), secrets.token_urlsafe(24), bool(enabled), actor_id))
    return get_state(client_id, actor_id, plan_id)


def public_by_token(token) -> dict:
    from ..cadu_family import repository
    if not available() or not token or len(str(token)) > 80:
        raise NotFound('Plano final não publicado.')
    rows = repository.rows('''SELECT f.version, f.document, f.created_at, p.title AS plan_title, p.advertiser_name
                                FROM cadu_planner_final_plan_shares s
                                JOIN cadu_planner_plans p ON p.id = s.plan_id AND p.archived_at IS NULL
                                JOIN LATERAL (SELECT version, document, created_at FROM cadu_planner_final_plans
                                               WHERE plan_id = s.plan_id ORDER BY version DESC LIMIT 1) f ON TRUE
                               WHERE s.share_token = %s AND s.share_enabled = TRUE LIMIT 1''', (str(token),))
    projection = public_projection(rows[0] if rows else None)
    if not projection:
        raise NotFound('Plano final não publicado.')
    return projection


def public_for_plan(plan_id) -> dict | None:
    """Final plan inside the plan's own shared link (the plan link is already public)."""
    try:
        if not available():
            return None
        latest = _latest(plan_id)
    except Exception:  # noqa: BLE001 — older schema: the shared plan still opens
        return None
    return public_projection(latest)


def add_to_project(client_id, actor_id, plan_id) -> dict:
    """Index the current version as project knowledge (same pipeline as chat notes)."""
    _require_available()
    from ..cadu_workspace.agent_v2.contracts import RequestContext
    from ..cadu_workspace import project_source_service
    from ..db import get_db
    plan, _payload = _context(client_id, actor_id, plan_id)
    latest = _latest(plan['id'])
    if not latest:
        raise BadRequest('Gere o plano final antes de adicioná-lo ao projeto.')
    project_ref = str(plan.get('project_ref') or '')
    if not project_ref.startswith('ci:'):
        raise BadRequest('Vincule o plano a um projeto do Cadu para adicioná-lo como conhecimento.')
    context = RequestContext(client_id=client_id, user_id=actor_id, conversation_id=None, surface='planner',
                             project_ref=project_ref)
    title = f"Plano final — {plan.get('title') or 'Plano'} (v{latest['version']})"
    result = project_source_service.create_note(context, title=title[:180],
                                                content=to_markdown(latest['document'], plan.get('title') or ''),
                                                category='media_plan')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('UPDATE cadu_planner_final_plans SET project_source_id = %s WHERE id = %s',
                    (result.get('source_id'), str(latest['id'])))
    state = get_state(client_id, actor_id, plan_id)
    state['project'] = {'source_id': result.get('source_id'), 'charged_credits': result.get('charged_credits'),
                        'project_ref': project_ref}
    return state
