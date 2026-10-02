"""Contratos comuns do Radar: toda fonte vira um Signal; sinais viram Opportunity."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SOURCE_TYPES = ('news', 'search_trend', 'social', 'regulation', 'event', 'crm', 'report', 'other')
QUADRANTS = ('conteudo', 'midia', 'integrada', 'ignorar')
OPPORTUNITY_STATUSES = ('nova', 'salva', 'em_plano', 'descartada')
VERDICTS = ('confirmado', 'parcial', 'contestado', 'nao_verificado')


@dataclass
class Evidence:
    url: str
    title: str = ''
    excerpt: str = ''
    published_at: str | None = None
    primary_source: bool = False


@dataclass
class Verification:
    """Resultado do agente verificador, que tenta provar que o sinal está errado."""
    verdict: str = 'nao_verificado'
    is_recent: bool | None = None
    has_primary_source: bool | None = None
    corroborating_sources: int = 0
    out_of_context: bool | None = None
    notes: str = ''
    model: str | None = None

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(f'Veredito desconhecido: {self.verdict}')


@dataclass
class Signal:
    headline: str
    source: str
    source_type: str = 'news'
    url: str = ''
    description: str = ''
    published_at: str | None = None
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    geography: list[str] = field(default_factory=list)
    industry: str | None = None
    keywords: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    velocity: float = 0.0
    verification: Verification = field(default_factory=Verification)

    def __post_init__(self):
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f'Tipo de fonte desconhecido: {self.source_type}')
        if not 0 <= self.confidence <= 1:
            raise ValueError('Confiança deve estar entre 0 e 1.')

    def as_dict(self):
        return asdict(self)


@dataclass
class GeoScore:
    """Nota de uma praça. Cada dimensão vai de 0 a 100."""
    place: str
    level: str = 'cidade'
    interest: float = 0
    audience: float = 0
    owned_base: float = 0
    media_history: float = 0
    competition: float = 0
    coverage: float = 0
    context: float = 0
    business_goal: float = 0
    score: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    """Critérios (0–100), o peso de cada um, penalidades e a nota final."""
    criteria: dict[str, float]
    weights: dict[str, float]
    penalties: dict[str, float] = field(default_factory=dict)
    score: int = 0


@dataclass
class Opportunity:
    title: str
    thesis: str
    signal_ids: list[str] = field(default_factory=list)
    editorial: ScoreBreakdown | None = None
    paid: ScoreBreakdown | None = None
    geo: list[GeoScore] = field(default_factory=list)
    quadrant: str = 'ignorar'
    status: str = 'nova'
    brand_ref: str | None = None
    project_ref: str | None = None

    def __post_init__(self):
        if self.quadrant not in QUADRANTS:
            raise ValueError(f'Quadrante desconhecido: {self.quadrant}')
        if self.status not in OPPORTUNITY_STATUSES:
            raise ValueError(f'Status desconhecido: {self.status}')

    def as_dict(self):
        return asdict(self)
