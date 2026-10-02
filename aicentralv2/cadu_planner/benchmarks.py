"""Media Benchmark Engine: a IA interpreta, a matemática calcula.

Toda estimativa sai como faixa (baixo, provável, alto), nunca como um número
com falsa precisão. Benchmarks guardam P25/P50/P75 e a origem do número:
``history`` (campanhas reais) ou ``model_estimate`` (estimativa revisada).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

SOURCES = ('history', 'model_estimate')
METRICS = ('cpm', 'cpc', 'ctr', 'cpa', 'frequency')

# Fatores dos três cenários de verba sobre a verba de referência.
SCENARIOS = (
    ('teste', 'Teste', 'Menor investimento para validar a hipótese.', 0.35),
    ('recomendado', 'Recomendado', 'Investimento para gerar cobertura relevante.', 1.0),
    ('amplificacao', 'Amplificação', 'Maior investimento caso o sinal confirme performance.', 2.2),
)


@dataclass(frozen=True)
class Range:
    low: float
    mid: float
    high: float

    def __post_init__(self):
        if not (self.low <= self.mid <= self.high):
            raise ValueError('Faixa inválida: esperado low <= mid <= high.')

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Benchmark:
    channel: str
    metric: str
    p25: float
    p50: float
    p75: float
    source: str
    sample_size: int = 0
    reviewed: bool = False
    objective: str = 'any'
    geo: str = 'BR'

    def __post_init__(self):
        if self.metric not in METRICS:
            raise ValueError(f'Métrica desconhecida: {self.metric}')
        if self.source not in SOURCES:
            raise ValueError(f'Origem desconhecida: {self.source}')
        Range(self.p25, self.p50, self.p75)

    @property
    def range(self) -> Range:
        return Range(self.p25, self.p50, self.p75)


def impressions(budget: float, cpm: float) -> float:
    """Impressões = verba ÷ CPM × 1000."""
    if cpm <= 0:
        raise ValueError('CPM deve ser positivo.')
    return max(0.0, float(budget)) / float(cpm) * 1000


def reach(total_impressions: float, frequency: float) -> float:
    """Alcance = impressões ÷ frequência (aproximação linear; curvas reais saturam)."""
    return max(0.0, float(total_impressions)) / max(1.0, float(frequency))


def reach_estimate(budget: float, cpm: Range, frequency: Range) -> dict:
    """Faixas de impressões e alcance para uma verba.

    O cenário otimista usa o CPM baixo e a frequência baixa; o conservador, o
    CPM alto e a frequência alta. Assim a faixa nunca esconde a incerteza.
    """
    imp = Range(impressions(budget, cpm.high), impressions(budget, cpm.mid), impressions(budget, cpm.low))
    people = Range(reach(imp.low, frequency.high), reach(imp.mid, frequency.mid), reach(imp.high, frequency.low))
    return {
        'budget': float(budget),
        'impressions': _rounded(imp),
        'reach': _rounded(people),
        'frequency': frequency.as_dict(),
        'cpm': cpm.as_dict(),
        'note': 'Estimativa intervalar. São previsões, não promessas.',
    }


def scenarios(reference_budget: float, cpm: Range, frequency: Range) -> list[dict]:
    """Os três cenários de investimento (Teste, Recomendado, Amplificação)."""
    if reference_budget <= 0:
        return []
    return [{
        'id': key, 'label': label, 'description': description,
        **reach_estimate(round(reference_budget * factor, 2), cpm, frequency),
    } for key, label, description, factor in SCENARIOS]


def split_budget(total: float, weights: dict[str, float]) -> dict[str, float]:
    """Distribui a verba pelos pesos (percentuais ou relativos) sem perder centavos."""
    positive = {key: float(value) for key, value in weights.items() if float(value or 0) > 0}
    if total <= 0 or not positive:
        return {key: 0.0 for key in weights}
    scale = sum(positive.values())
    result = {key: round(total * positive.get(key, 0) / scale, 2) for key in weights}
    drift = round(total - sum(result.values()), 2)
    if drift:
        largest = max(positive, key=positive.get)
        result[largest] = round(result[largest] + drift, 2)
    return result


def _rounded(value: Range) -> dict:
    return {'low': int(value.low), 'mid': int(value.mid), 'high': int(value.high)}
