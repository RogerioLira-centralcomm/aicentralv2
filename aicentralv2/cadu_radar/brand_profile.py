"""Completar o perfil da marca: um fluxo separado do Radar, que pesquisa, propõe e só grava o que o usuário aprovar.

O Radar usa o perfil da marca (concorrentes, posicionamento, público). Quando falta, em vez de travar a busca,
este fluxo pesquisa na web, mostra a proposta e, ao salvar, **acrescenta** ao que já existe: listas são mescladas
sem repetir, texto já preenchido só é trocado se o usuário pedir, e cada atualização fica registrada no próprio perfil.
Quem grava é o gravador oficial do perfil (``CreativeModelingRepository.update_client_brand_profile``), que mescla só
as chaves enviadas e nunca mexe em ``design_system_ads``.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from . import prompts
from .research import json_loads

PROMPTS = '1.5'
TEXT_FIELDS = ('positioning', 'target_audience')
GAP_FIELDS = (('competitors', 'Concorrentes'), ('positioning', 'Posicionamento'), ('target_audience', 'Público-alvo'))
MAX_COMPETITORS = 20
USD_ESTIMATE = 0.05
HISTORY_LIMIT = 10


def _clean(text, limit):
    """Texto de resposta com busca na web: tira as marcas de nota de rodapé ("[2]") e os espaços repetidos."""
    return ' '.join(re.sub(r'\[\d+\]', '', str(text or '')).split())[:limit]


def _plain(text):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(text or '').casefold()) if not unicodedata.combining(ch)).strip()


def _brand_id(brand_ref):
    if not str(brand_ref or '').startswith('studio:'):
        raise BadRequest('Escolha uma marca.')
    try:
        return int(str(brand_ref).split(':', 1)[1])
    except ValueError:
        raise BadRequest('Marca inválida.') from None


def load_brand(client_id, brand_ref):
    rows = repository.rows('''SELECT id, name, sector, website_url, COALESCE(brand_profile, '{}'::jsonb) AS brand_profile
                                FROM cx_clients WHERE id = %s AND crm_client_id = %s''', (_brand_id(brand_ref), int(client_id)))
    if not rows:
        raise NotFound('Marca indisponível.')
    return rows[0]


def competitor_items(value):
    """Concorrentes do perfil como ``[{'name', 'description'}]``, qualquer que seja o formato guardado."""
    if isinstance(value, str):
        value = [part.strip() for part in value.replace('\n', ',').split(',') if part.strip()]
    items = []
    for entry in value if isinstance(value, (list, tuple)) else []:
        if isinstance(entry, dict):
            name = entry.get('name') or entry.get('nome') or entry.get('title') or entry.get('label')
            description = entry.get('description') or entry.get('descricao') or entry.get('summary') or ''
        else:
            name, description = entry, ''
        name = ' '.join(str(name or '').split())
        if name:
            items.append({'name': name[:120], 'description': ' '.join(str(description or '').split())[:300]})
    return items


def _filled(profile, key):
    value = profile.get(key)
    return bool(competitor_items(value)) if key == 'competitors' else bool(str(value or '').strip())


def gaps(profile):
    """Campos que o Radar usa e que o perfil ainda não tem."""
    return [{'key': key, 'label': label} for key, label in GAP_FIELDS if not _filled(profile or {}, key)]


def _now():
    return datetime.now(timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo'))


def propose(client_id, actor_id, brand_ref):
    """Pesquisa na web (Perplexity via OpenRouter, cobrado pelo custo) e devolve a proposta, sem gravar nada."""
    from ..cadu_planner.context import load_plan_context
    from ..services.cadu_ai_connector import CaduAIConnector
    from ..services.openrouter_service import message_text
    from .pipeline import usd_to_tokens
    brand = load_brand(client_id, brand_ref)
    profile = brand['brand_profile'] or {}
    existing = competitor_items(profile.get('competitors'))
    known = '; '.join(filter(None, [
        f"concorrentes: {', '.join(item['name'] for item in existing)}" if existing else '',
        f"posicionamento: {profile['positioning']}" if str(profile.get('positioning') or '').strip() else '']))
    context = load_plan_context(client_id, brand_ref, None)
    summary = (context.get('brand') or {}).get('fields') or []
    system, user = prompts.messages('brand_profile', PROMPTS, today=_now().date().isoformat(), brand_name=brand['name'],
                                    site=brand.get('website_url') or 'não informado', sector=brand.get('sector') or 'não informado',
                                    known=known or 'nada ainda')
    result = CaduAIConnector().complete(
        [system, user], client_id=int(client_id), user_id=int(actor_id), idempotency_key=f'radar-brand:{client_id}:{brand["id"]}:{uuid4()}',
        app='Cadu Radar', stage='radar:brand-profile', estimated_tokens=max(1, usd_to_tokens(client_id, USD_ESTIMATE)),
        model='perplexity/sonar', metadata={'brand_id': brand['id'], 'prompt_version': PROMPTS},
        max_tokens=2500, timeout=120, temperature=0.2, provider='openrouter')
    data = json_loads(message_text(result.get('message')))
    known_names = {_plain(item['name']) for item in existing}
    proposed = []
    for entry in data.get('concorrentes') or []:
        if isinstance(entry, dict) and entry.get('nome'):
            name = _clean(entry['nome'], 120)
            proposed.append({'name': name, 'description': _clean(entry.get('motivo'), 300),
                             'is_new': _plain(name) not in known_names})
    return {
        'brand': {'ref': brand_ref, 'name': brand['name']},
        'competitors': proposed[:6],
        'positioning': _clean(data.get('posicionamento'), 600),
        'target_audience': _clean(data.get('publico'), 600),
        'sources': [str(url) for url in data.get('fontes') or [] if str(url).startswith('http')][:8],
        'existing': {'competitors': [item['name'] for item in existing], 'positioning': str(profile.get('positioning') or '').strip(),
                     'target_audience': str(profile.get('target_audience') or '').strip()[:400]},
        'gaps': gaps(profile), 'known_fields': [item['label'] for item in summary][:8],
        'cost_tokens': int((result.get('cadu_charge') or {}).get('tokens_cobrados') or 0)}


def merge_competitors(existing, new):
    """Acrescenta sem repetir e sem tocar no que já está lá."""
    merged = competitor_items(existing)
    seen = {_plain(item['name']) for item in merged}
    for item in competitor_items(new):
        if _plain(item['name']) not in seen and len(merged) < MAX_COMPETITORS:
            merged.append(item)
            seen.add(_plain(item['name']))
    return merged


def build_update(profile, *, competitors=None, positioning=None, target_audience=None, replace=None, sources=None, actor_id=None):
    """Chaves do perfil que mudam (e só elas), segundo as regras: lista soma, texto preenchido só troca se pedido."""
    replace = replace if isinstance(replace, dict) else {}
    changes, changed = {}, []
    merged = merge_competitors(profile.get('competitors'), competitors)
    if merged != competitor_items(profile.get('competitors')):
        changes['competitors'] = merged
        changed.append('competitors')
    for key, value in (('positioning', positioning), ('target_audience', target_audience)):
        text = ' '.join(str(value or '').split())[:600]
        if text and (not _filled(profile, key) or replace.get(key) is True) and text != str(profile.get(key) or '').strip():
            changes[key] = text
            changed.append(key)
    if not changed:
        return {}, []
    stamp = _now().isoformat()
    urls = [str(url) for url in sources or [] if str(url).startswith('http')][:8]
    # A proveniência fica só em radar_enrichment, chave que apenas este fluxo escreve: field_provenance é de outros
    # fluxos (auditoria de marca) e seus estados de evidência são fechados, então não é regravado aqui.
    enrichment = profile.get('radar_enrichment') or {}
    history = list(enrichment.get('history') or [])
    history.append({'at': stamp, 'by': actor_id, 'fields': changed, 'sources': urls})
    sources_by_field = dict(enrichment.get('sources') or {})
    for key in changed:
        sources_by_field[key] = {'urls': urls, 'updated_at': stamp}
    changes['radar_enrichment'] = {'updated_at': stamp, 'sources': sources_by_field, 'history': history[-HISTORY_LIMIT:]}
    return changes, changed


def save(client_id, actor_id, brand_ref, **fields):
    """Grava o que o usuário aprovou, mesclando com o perfil atual. Devolve o que mudou e o que ainda falta."""
    from ..creative_modeling_repository import CreativeModelingRepository
    brand = load_brand(client_id, brand_ref)
    profile = brand['brand_profile'] or {}
    changes, changed = build_update(profile, actor_id=actor_id, **fields)
    if changes:
        CreativeModelingRepository().update_client_brand_profile(brand['id'], changes)
    after = {**profile, **changes}
    return {'changed': changed, 'gaps': gaps(after), 'competitors': [item['name'] for item in competitor_items(after.get('competitors'))]}
