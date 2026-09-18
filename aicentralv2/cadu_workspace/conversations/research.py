"""Paid web-research stage used by explicit Workspace conversation starters.

The provider gathers current, cited evidence; Dify remains the project agent that
turns that evidence into a decision.  Keeping the two stages separate prevents a
web result from being presented as an unreviewed project recommendation.
"""
from __future__ import annotations

import json
import os
import re

from ...services.openrouter_service import OpenRouterError, chat_completion, message_text


PLANS = {
    'market': {
        'model': os.getenv('CADU_MARKET_RESEARCH_MODEL', 'perplexity/sonar-pro'),
        'estimate_tokens': 900,
        'reserve_tokens': 30000,
        'max_tokens': 1800,
        'label': 'Atualização de mercado',
    },
    'deep': {
        'model': os.getenv('CADU_DEEP_RESEARCH_MODEL', 'perplexity/sonar-pro'),
        'estimate_tokens': 4200,
        'reserve_tokens': 60000,
        'max_tokens': 6000,
        'label': 'Pesquisa aprofundada',
    },
}


class ResearchUnavailable(RuntimeError):
    pass


def plan_for(query: str, depth: str = 'analysis') -> dict | None:
    text = str(query or '').casefold()
    if re.search(r'\b(deep research|pesquisa aprofundada|pesquisa profunda)\b', text):
        return {'id': 'deep', **PLANS['deep']}
    if re.search(r'\b(atualiza[çc][ãa]o de mercado|atualize o mercado|mercado recente)\b', text):
        return {'id': 'market', **PLANS['market']}
    # This is the explicit, paid depth control from the composer. It is not a
    # cosmetic “better model” switch: it enables the bounded evidence stage
    # before the main agent receives the request.
    if depth == 'deep':
        return {'id': 'deep', **PLANS['deep']}
    return None


def _project_snapshot(project_context: str) -> dict:
    try:
        packet = json.loads(project_context or '{}')
    except (TypeError, ValueError):
        return {}
    private = packet.get('contexto_projeto_privado') if isinstance(packet, dict) else {}
    return private if isinstance(private, dict) else {}


def _research_target(project_context: str) -> dict:
    """Return the bounded project context that makes research actionable.

    Research must start from everything the team has already recorded for the
    selected project. The official site is a lead for primary sources; a
    timeout or inaccessible page must never turn into a request for the user
    to supply sources.
    """
    snapshot = _project_snapshot(project_context)
    project = snapshot.get('projeto') if isinstance(snapshot.get('projeto'), dict) else {}
    brand = snapshot.get('marca') if isinstance(snapshot.get('marca'), dict) else {}
    sources = snapshot.get('fontes_verificadas') if isinstance(snapshot.get('fontes_verificadas'), list) else []
    return {
        'marca': {
            'nome': str(brand.get('name') or '')[:160],
            'setor': str(brand.get('sector') or '')[:120],
            'site_oficial': str(brand.get('website_url') or '')[:1200],
            'perfil': brand.get('brand_profile') if isinstance(brand.get('brand_profile'), dict) else {},
        },
        'projeto': {
            'nome': str(project.get('nome') or '')[:200],
            'descricao': str(project.get('descricao') or '')[:1200],
            'instrucoes': str(project.get('instrucoes') or '')[:2400],
            'publico': str(project.get('publico') or '')[:600],
            'posicionamento': str(project.get('posicionamento') or '')[:600],
            'tom_de_voz': str(project.get('tom_de_voz') or '')[:400],
        },
        'fontes_ja_vinculadas': [
            {'fonte': str(source.get('fonte') or '')[:250], 'trecho': str(source.get('trecho') or '')[:1000]}
            for source in sources[:8] if isinstance(source, dict)
        ],
    }


def execute(plan: dict, query: str, project_context: str) -> dict:
    """Return provider evidence in a compact, attributable envelope."""
    prompt = {
        'pedido_do_usuario': str(query or '')[:4000],
        'alvo_da_pesquisa': _research_target(project_context),
        'entrega': (
            'Pesquise apenas informações públicas recentes e relevantes. Para cada achado, '
            'inclua fonte, URL, data (ou indique quando não houver) e por que isso importa. '
            'Separe fatos de inferências e nunca invente números ou citações. O site oficial, '
            'quando informado, serve para identificar a marca e localizar fontes primárias; não '
            'depende de conseguir abri-lo e não é motivo para interromper a pesquisa. Não peça '
            'ao usuário links, período ou recorte que já possam ser tratados como premissa: entregue '
            'a melhor atualização com fontes públicas disponíveis e explicite apenas limitações reais.'
        ),
    }
    try:
        response = chat_completion([
            {'role': 'system', 'content': 'Você é um pesquisador criterioso de mercado. Responda em português do Brasil com fontes verificáveis.'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ], model=plan['model'], max_tokens=plan['max_tokens'], temperature=0.1,
           timeout=150, provider='openrouter')
    except OpenRouterError as exc:
        raise ResearchUnavailable(str(exc) or 'A pesquisa externa não respondeu.') from exc
    message = response.get('message') if isinstance(response, dict) else {}
    citations = message.get('citations') if isinstance(message, dict) else []
    sources = []
    for citation in citations if isinstance(citations, list) else []:
        if isinstance(citation, str) and citation.startswith(('https://', 'http://')):
            sources.append({'title': citation, 'url': citation, 'excerpt': ''})
        elif isinstance(citation, dict):
            url = str(citation.get('url') or citation.get('source') or '')[:1200]
            if url.startswith(('https://', 'http://')):
                sources.append({'title': str(citation.get('title') or url)[:250], 'url': url,
                                'excerpt': str(citation.get('text') or citation.get('snippet') or '')[:700]})
    return {
        'plan': plan['id'], 'label': plan['label'], 'content': message_text(message)[:30000],
        'sources': sources[:10], 'provider_result': response,
    }


def attach(project_context: str, research: dict) -> str:
    """Expose research to the agent as evidence, not as private project truth."""
    try:
        packet = json.loads(project_context or '{}')
    except (TypeError, ValueError):
        packet = {}
    if not isinstance(packet, dict):
        packet = {}
    packet['pesquisa_externa_atual'] = {
        'tipo': research.get('label'), 'evidencia': research.get('content'),
        'fontes': research.get('sources') or [],
        'orientacao': 'Trate como evidência externa recente: cite a fonte e diferencie fatos de inferências.',
    }
    # Dify receives a bounded JSON variable. Keep the source-bearing research
    # useful without turning a paid research result into an oversized request.
    packet['pesquisa_externa_atual']['evidencia'] = str(research.get('content') or '')[:6000]
    serialized = json.dumps(packet, ensure_ascii=False)
    if len(serialized) <= 24000:
        return serialized
    packet['base_cadu_global_publicada'] = (packet.get('base_cadu_global_publicada') or [])[:1]
    packet['workspace_da_equipe'] = {}
    packet['pesquisa_externa_atual']['evidencia'] = str(research.get('content') or '')[:3000]
    serialized = json.dumps(packet, ensure_ascii=False)
    if len(serialized) <= 24000:
        return serialized
    private = packet.get('contexto_projeto_privado')
    if isinstance(private, dict):
        private['fontes_verificadas'] = (private.get('fontes_verificadas') or [])[:2]
    serialized = json.dumps(packet, ensure_ascii=False)
    if len(serialized) <= 24000:
        return serialized
    project = private.get('projeto') if isinstance(private, dict) else {}
    project = project if isinstance(project, dict) else {}
    minimal = {
        'contexto_projeto_privado': {
            'projeto_ref': str((private or {}).get('projeto_ref') or '')[:100],
            'projeto': {key: str(project.get(key) or '')[:1200]
                        for key in ('nome', 'descricao', 'instrucoes', 'publico', 'posicionamento', 'tom_de_voz')},
        },
        'pesquisa_externa_atual': {
            **packet['pesquisa_externa_atual'],
            'evidencia': str(packet['pesquisa_externa_atual'].get('evidencia') or '')[:1800],
            'fontes': (packet['pesquisa_externa_atual'].get('fontes') or [])[:4],
        },
    }
    return json.dumps(minimal, ensure_ascii=False)


def attach_unavailable(project_context: str, plan: dict) -> str:
    """Keep the agent grounded when optional current research cannot run.

    This deliberately contains no provider error, status code, credential or
    balance detail: it is an instruction about evidence quality, not a
    customer-facing operational explanation.
    """
    try:
        packet = json.loads(project_context or '{}')
    except (TypeError, ValueError):
        packet = {}
    if not isinstance(packet, dict):
        packet = {}
    packet['pesquisa_externa_atual'] = {
        'tipo': str((plan or {}).get('label') or 'Pesquisa externa')[:160],
        'status': 'nao_consultada_nesta_resposta',
        'orientacao': (
            'Não apresente atualização externa como fato nesta resposta. '
            'Use o contexto já registrado e diferencie premissas de evidências.'
        ),
    }
    return json.dumps(packet, ensure_ascii=False)[:24000]
