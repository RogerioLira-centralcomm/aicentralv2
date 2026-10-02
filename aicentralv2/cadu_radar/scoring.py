"""Notas do Radar: determinísticas, explicáveis e separadas.

O modelo de linguagem só preenche os critérios (0–100) com justificativa. Os
pesos, as penalidades e o quadrante são calculados aqui, em Python, para que a
mesma evidência sempre gere a mesma nota.
"""
from __future__ import annotations

from .contracts import GeoScore, ScoreBreakdown

EDITORIAL_WEIGHTS = {
    'icp': 20,            # o assunto importa para o ICP da marca
    'marca': 15,          # combina com a marca e o tom
    'territorio': 15,     # está no território que a marca quer ocupar
    'autoridade': 15,     # a marca tem algo crível a dizer
    'cultura': 10,        # conversa cultural relevante
    'timing': 15,         # janela de tempo ainda aberta
    'conversa': 10,       # potencial de gerar conversa
}

PAID_WEIGHTS = {
    'icp': 20,            # afinidade com o ICP
    'audiencia': 15,      # volume de audiência comprável
    'geo': 15,            # fit geográfico
    'momentum': 10,       # o assunto está crescendo
    'criativo': 15,       # potencial criativo
    'eficiencia': 15,     # eficiência estimada (custo x resultado)
    'canais': 10,         # fit com os canais disponíveis
}

GEO_WEIGHTS = {
    'interest': 20, 'audience': 15, 'owned_base': 15, 'media_history': 10,
    'competition': 10, 'coverage': 10, 'context': 10, 'business_goal': 10,
}

# Penalidade máxima por motivo, em pontos subtraídos da nota final.
PENALTY_CAPS = {
    'saturacao': 15,
    'custo_excessivo': 15,
    'baixa_confianca': 20,
    'restricao_marca': 30,
    'risco_reputacional': 30,
    'pouca_evidencia': 20,
}

HIGH_THRESHOLD = 70

QUADRANT_LABELS = {
    'integrada': 'Iniciar a conversa no orgânico e amplificar com mídia.',
    'conteudo': 'Excelente oportunidade para conteúdo.',
    'midia': 'Existe audiência e contexto de mídia.',
    'ignorar': 'Não merece investimento agora.',
}


def _clamp(value, low=0.0, high=100.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def weighted(criteria: dict, weights: dict, penalties: dict | None = None) -> ScoreBreakdown:
    """Média ponderada dos critérios menos penalidades, limitada a 0–100.

    Critério ausente conta como 0: falta de evidência nunca vira nota alta.
    """
    unknown = set(criteria) - set(weights)
    if unknown:
        raise ValueError('Critérios desconhecidos: ' + ', '.join(sorted(unknown)))
    total_weight = sum(weights.values())
    clean = {key: _clamp(criteria.get(key, 0)) for key in weights}
    base = sum(clean[key] * weight for key, weight in weights.items()) / total_weight
    applied = {}
    for reason, value in (penalties or {}).items():
        if reason not in PENALTY_CAPS:
            raise ValueError(f'Penalidade desconhecida: {reason}')
        points = _clamp(value, 0, PENALTY_CAPS[reason])
        if points:
            applied[reason] = points
    score = int(round(_clamp(base - sum(applied.values()))))
    return ScoreBreakdown(criteria=clean, weights=dict(weights), penalties=applied, score=score)


def editorial_score(criteria: dict, penalties: dict | None = None) -> ScoreBreakdown:
    return weighted(criteria, EDITORIAL_WEIGHTS, penalties)


def paid_score(criteria: dict, penalties: dict | None = None) -> ScoreBreakdown:
    return weighted(criteria, PAID_WEIGHTS, penalties)


def geo_score(place: GeoScore) -> GeoScore:
    """Preenche ``place.score`` a partir das oito dimensões da praça."""
    values = {key: getattr(place, key) for key in GEO_WEIGHTS}
    place.score = weighted(values, GEO_WEIGHTS).score
    return place


def rank_places(places: list[GeoScore]) -> list[GeoScore]:
    """Praças ordenadas pela nota. Maior audiência não vence sozinha."""
    return sorted((geo_score(place) for place in places), key=lambda item: (-item.score, item.place))


def quadrant(editorial: int, paid: int, threshold: int = HIGH_THRESHOLD) -> str:
    """Matriz Orgânico × Pago.

                     pago baixo   pago alto
    orgânico alto    conteudo     integrada
    orgânico baixo   ignorar      midia
    """
    high_editorial, high_paid = editorial >= threshold, paid >= threshold
    if high_editorial and high_paid:
        return 'integrada'
    if high_editorial:
        return 'conteudo'
    if high_paid:
        return 'midia'
    return 'ignorar'
