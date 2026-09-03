"""
Formatadores para conversão de dados em formato ApexCharts (categories + series).
Utilizado pelo dashboard comercial para evitar transformações no frontend.
"""

MONTH_LABELS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# Paleta de cores consistente com o design system
PALETTE = {
    'primary': '#1e4d4f',
    'secondary': '#64748b',
    'blue': '#2563eb',
    'violet': '#7c3aed',
    'cyan': '#0e7490',
    'rose': '#be123c',
    'amber': '#b45309',
}

# Cores por status de cotação
STATUS_COLORS = {
    'aprovada': PALETTE['primary'],
    'enviada': PALETTE['blue'],
    'rejeitada': PALETTE['rose'],
    'recusada': PALETTE['rose'],
    'expirada': PALETTE['amber'],
    'rascunho': PALETTE['secondary'],
    'em acompanhamento': PALETTE['cyan'],
}

PALETTE_LIST = [
    '#1e4d4f', '#2563eb', '#7c3aed', '#0e7490',
    '#475569', '#4f46e5', '#0f766e', '#334155'
]


def _status_color(status, index=0):
    """Retorna cor para um status de cotação."""
    normalized = str(status or '').strip().lower()
    for key, color in STATUS_COLORS.items():
        if key in normalized:
            return color
    return PALETTE_LIST[index % len(PALETTE_LIST)]


def format_overview_chart(geral_mensal):
    """
    Formata dados para o gráfico misto de visão geral.
    Barras empilhadas para carteira (clientes finais + agências).
    Linhas para cotações e PIs.
    """
    if not geral_mensal:
        return {'categories': MONTH_LABELS, 'series': []}

    return {
        'categories': MONTH_LABELS,
        'series': [
            {
                'name': 'Clientes finais',
                'type': 'bar',
                'data': [int(row.get('clientes_finais') or 0) for row in geral_mensal],
                'color': PALETTE['primary'],
            },
            {
                'name': 'Agências',
                'type': 'bar',
                'data': [int(row.get('agencias') or 0) for row in geral_mensal],
                'color': PALETTE['secondary'],
            },
            {
                'name': 'Cotações',
                'type': 'line',
                'data': [int(row.get('cotacoes') or 0) for row in geral_mensal],
                'color': PALETTE['blue'],
            },
            {
                'name': 'PIs',
                'type': 'line',
                'data': [int(row.get('pis') or 0) for row in geral_mensal],
                'color': PALETTE['violet'],
            },
        ],
    }


def format_quotes_chart(cotacoes_semanais, statuses):
    """
    Formata dados para o gráfico de cotações semanais por status.
    Barras empilhadas por status.
    """
    if not cotacoes_semanais or not statuses:
        return {'categories': [], 'series': []}

    return {
        'categories': [row.get('rotulo', '') for row in cotacoes_semanais],
        'series': [
            {
                'name': status,
                'data': [
                    int((row.get('status') or {}).get(status, {}).get('quantidade') or 0)
                    for row in cotacoes_semanais
                ],
                'currencyValues': [
                    float((row.get('status') or {}).get(status, {}).get('valor_total') or 0)
                    for row in cotacoes_semanais
                ],
                'color': _status_color(status, index),
            }
            for index, status in enumerate(statuses)
        ],
    }


def format_campaigns_chart(campanhas_mensal, plataformas):
    """
    Formata dados para o gráfico de campanhas por plataforma.
    Barras empilhadas por plataforma.
    """
    if not campanhas_mensal or not plataformas:
        return {'categories': MONTH_LABELS, 'series': []}

    # Filtrar plataformas com total > 0 e ordenar por volume
    active_platforms = []
    for platform in plataformas:
        total = sum(
            int((row.get('plataformas') or {}).get(platform) or 0)
            for row in campanhas_mensal
        )
        if total > 0:
            active_platforms.append({'name': platform, 'total': total})

    active_platforms.sort(key=lambda x: -x['total'])

    return {
        'categories': MONTH_LABELS,
        'series': [
            {
                'name': platform['name'],
                'data': [
                    int((row.get('plataformas') or {}).get(platform['name']) or 0)
                    for row in campanhas_mensal
                ],
                'color': PALETTE_LIST[index % len(PALETTE_LIST)],
            }
            for index, platform in enumerate(active_platforms)
        ],
    }


def format_executive_portfolio(carteira):
    """
    Formata dados para o gráfico de carteira do executivo.
    Barras horizontais empilhadas (ativos + prospecção).
    """
    if not carteira:
        return {
            'categories': ['Clientes finais', 'Agências'],
            'series': [
                {'name': 'Ativos', 'data': [0, 0], 'color': PALETTE['primary']},
                {'name': 'Prospecção', 'data': [0, 0], 'color': PALETTE['blue']},
            ],
        }

    clientes_finais = carteira.get('clientes_finais') or {}
    agencias = carteira.get('agencias') or {}

    return {
        'categories': ['Clientes finais', 'Agências'],
        'series': [
            {
                'name': 'Ativos',
                'data': [
                    int(clientes_finais.get('ativo') or 0),
                    int(agencias.get('ativo') or 0),
                ],
                'color': PALETTE['primary'],
            },
            {
                'name': 'Prospecção',
                'data': [
                    int(clientes_finais.get('prospeccao') or 0),
                    int(agencias.get('prospeccao') or 0),
                ],
                'color': PALETTE['blue'],
            },
        ],
    }


def format_executive_line(mensal, field, color_key='blue'):
    """
    Formata dados para gráfico de linha do executivo (cotações ou PIs).
    """
    if not mensal:
        return {
            'categories': MONTH_LABELS,
            'series': [{'name': field.capitalize(), 'data': [0] * 12, 'color': PALETTE.get(color_key, PALETTE['blue'])}],
        }

    return {
        'categories': MONTH_LABELS,
        'series': [
            {
                'name': field.capitalize(),
                'data': [int(row.get(field) or 0) for row in mensal],
                'color': PALETTE.get(color_key, PALETTE['blue']),
            }
        ],
    }


def format_executives_apex(executivos):
    """
    Formata todos os gráficos de executivos para ApexCharts.
    Retorna lista com portfolio, quotes e pis formatados para cada executivo.
    """
    result = []
    for executive in (executivos or [])[:3]:
        result.append({
            'portfolio': format_executive_portfolio(executive.get('carteira')),
            'quotes': format_executive_line(executive.get('mensal'), 'cotacoes', 'blue'),
            'pis': format_executive_line(executive.get('mensal'), 'pis', 'violet'),
        })
    return result
