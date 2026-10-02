"""Etapas do Radar. Implementação na Fase 3; aqui ficam ordem e responsabilidades.

    discover  Perplexity via OpenRouter (cadu_workspace/insights_research.py)  — "Descubra."
    extract   Firecrawl web.read (cadu_workspace/web_search.py)               — "Leia e estruture."
    verify    segundo modelo via OpenRouter                                   — "Prove que está errado."
    signals   normaliza tudo no contrato Signal (contracts.py)
    cluster   agrupa sinais do mesmo acontecimento
    judge     preenche critérios e calcula notas em scoring.py (Editorial, Paga, Geo)

O run roda em thread daemon com lease no banco (padrão de agent_v2/long_jobs),
reserva créditos antes de cada chamada paga e nunca promete monitoramento contínuo.
"""
from __future__ import annotations

from flask import current_app

STEPS = (
    ('discover', 'Descobrindo sinais'),
    ('extract', 'Lendo as fontes'),
    ('verify', 'Verificando as evidências'),
    ('signals', 'Organizando os sinais'),
    ('cluster', 'Agrupando acontecimentos'),
    ('judge', 'Avaliando oportunidades'),
)


class RadarDisabled(RuntimeError):
    pass


def enabled() -> bool:
    return bool(current_app.config.get('CADU_RADAR_ENABLED'))


def start_run(client_id, actor_id, *, brand_ref=None, project_ref=None):
    if not enabled():
        raise RadarDisabled('O Radar de Oportunidades ainda não está habilitado neste ambiente.')
    raise NotImplementedError('O pipeline do Radar entra na Fase 3.')
