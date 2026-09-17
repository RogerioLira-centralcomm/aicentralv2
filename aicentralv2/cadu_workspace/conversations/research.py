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


def plan_for(query: str) -> dict | None:
    text = str(query or '').casefold()
    if re.search(r'\b(deep research|pesquisa aprofundada|pesquisa profunda)\b', text):
        return {'id': 'deep', **PLANS['deep']}
    if re.search(r'\b(atualiza[çc][ãa]o de mercado|atualize o mercado|mercado recente)\b', text):
        return {'id': 'market', **PLANS['market']}
    return None


def _project_snapshot(project_context: str) -> dict:
    try:
        packet = json.loads(project_context or '{}')
    except (TypeError, ValueError):
        return {}
    private = packet.get('contexto_projeto_privado') if isinstance(packet, dict) else {}
    return private if isinstance(private, dict) else {}


def execute(plan: dict, query: str, project_context: str) -> dict:
    """Return provider evidence in a compact, attributable envelope."""
    snapshot = _project_snapshot(project_context)
    prompt = {
        'pedido_do_usuario': str(query or '')[:4000],
        'contexto_do_projeto': snapshot,
        'entrega': (
            'Pesquise apenas informações públicas recentes e relevantes. Para cada achado, '
            'inclua fonte, URL, data (ou indique quando não houver) e por que isso importa. '
            'Separe fatos de inferências e nunca invente números ou citações.'
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
