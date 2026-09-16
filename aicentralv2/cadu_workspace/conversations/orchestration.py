"""Deterministic, explainable routing for the shared Cadu chat.

This only selects an installed prompt posture; it never executes a tool or
changes the selected project.
"""
import re
import unicodedata


def _text(value):
    value = unicodedata.normalize('NFD', str(value or '').lower())
    return ''.join(char for char in value if not unicodedata.combining(char))


ROUTES = (
    ('planejamento', r'\b(plano|planejamento|media plan|orcamento|budget|cronograma|kpi|funil)\b'),
    ('analise', r'\b(analise|analisar|relatorio|resultado|performance|metricas|diagnostico)\b'),
    ('audiencias', r'\b(audiencia|publico|segmentacao|lookalike|persona|interesse)\b'),
    ('pesquisa', r'\b(pesquis[ae]|mercado|noticia|novidade|concorrente|tendencia)\b'),
    ('briefing', r'\b(briefing|brief|requisito|escopo)\b'),
    ('documento', r'\b(documento|pdf|proposta|smart doc|exporta)\b'),
    ('ideias', r'\b(ideia|conceito|criativo|campanha|hook|naming|ativacao)\b'),
)


def classify(message):
    """Return an intent and conservative complexity tier for telemetry."""
    text = _text(message)
    solution = next((name for name, pattern in ROUTES if re.search(pattern, text)), 'conversa')
    high = bool(re.search(r'\b(plano|planejamento|proposta|orcamento|budget|relatorio|diagnostico|estrategia)\b', text))
    medium = high or len(text) > 500 or solution in {'pesquisa', 'audiencias', 'briefing'}
    return {'solution': solution, 'complexity': 'alta' if high else 'media' if medium else 'baixa'}


def choose_mode(entries, message):
    """Choose a matching enabled skill, with the account default as fallback."""
    route = classify(message)
    entries = list(entries or [])
    by_id = {str(item.get('id')): item for item in entries if item.get('id')}
    aliases = {
        'planejamento': ('planejamento', 'planner'), 'analise': ('analise', 'análise'),
        'audiencias': ('audiencias', 'audiências', 'media_expert'),
        'pesquisa': ('media_expert', 'analise'), 'briefing': ('planejamento', 'analise'),
        'documento': ('planejamento', 'analise'), 'ideias': ('ideias',),
    }
    for candidate in aliases.get(route['solution'], ()):
        if candidate in by_id:
            return by_id[candidate], route
    active = next((item for item in entries if item.get('active')), None)
    return active or (entries[0] if entries else None), route
