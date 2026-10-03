"""Metric dictionary and pure calculations for the page detail view (Página 360).

Every number the page shows is declared here once, with its definition, unit, denominator and source, and the API
returns this dictionary next to the values so the screen never has to guess what a figure means.
"""

MIN_RELIABLE_SESSIONS = 30
RETENTION_DAYS = 90
DEVICE_LABELS = {'mobile': 'Celular', 'tablet': 'Tablet', 'desktop': 'Computador', 'unknown': 'Não identificado'}

DICTIONARY = [
    {'key': 'sessions', 'label': 'Sessões', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Sessões distintas com ao menos uma visualização desta página na janela.'},
    {'key': 'visitors', 'label': 'Visitantes únicos', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Visitantes distintos (cookie) que viram a página. Estimativa: depende do cookie do navegador (limpezas e navegação anônima contam como novos).'},
    {'key': 'views', 'label': 'Visualizações', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Total de eventos de visualização da página, incluindo recargas.'},
    {'key': 'entrances', 'label': 'Entradas', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Sessões cuja primeira página vista foi esta.'},
    {'key': 'exits', 'label': 'Saídas', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Sessões encerradas (30 min sem atividade) cuja última página vista foi esta.',
     'denominator': 'sessions'},
    {'key': 'exit_rate', 'label': 'Taxa de saída', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Saídas dividido por sessões da página. Sessões ainda em andamento não contam como saída.',
     'denominator': 'sessions'},
    {'key': 'single_page_rate', 'label': 'Visita de uma página', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Entradas em que a sessão viu somente esta página, dividido por entradas.',
     'denominator': 'entrances'},
    {'key': 'avg_active_seconds', 'label': 'Tempo ativo médio', 'unit': 'seconds', 'source': 'Super Tag',
     'definition': 'Média do tempo com a aba visível e em uso, medido na saída da página.',
     'denominator': 'measured_visits'},
    {'key': 'median_active_seconds', 'label': 'Tempo ativo mediano', 'unit': 'seconds', 'source': 'Super Tag',
     'definition': 'Mediana do mesmo tempo ativo; menos sensível a visitas muito longas.',
     'denominator': 'measured_visits'},
    {'key': 'scroll_25', 'label': 'Rolaram 25%', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Sessões que passaram de 25% da altura da página, dividido por sessões. Páginas sem rolagem não emitem o evento.',
     'denominator': 'sessions'},
    {'key': 'scroll_50', 'label': 'Rolaram 50%', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Idem, 50% da altura.', 'denominator': 'sessions'},
    {'key': 'scroll_75', 'label': 'Rolaram 75%', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Idem, 75% da altura.', 'denominator': 'sessions'},
    {'key': 'scroll_100', 'label': 'Rolaram até o fim', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Idem, 100% da altura.', 'denominator': 'sessions'},
    {'key': 'clicks', 'label': 'Cliques', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Cliques em links, botões e elementos marcados, incluindo WhatsApp.'},
    {'key': 'clicks_per_session', 'label': 'Cliques por sessão', 'unit': 'ratio', 'source': 'Super Tag',
     'definition': 'Cliques divididos por sessões.', 'denominator': 'sessions'},
    {'key': 'form_submits', 'label': 'Envios de formulário', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Formulários enviados nesta página. Nunca inclui o conteúdo dos campos.'},
    {'key': 'conversions_on_page', 'label': 'Conversões na página', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Eventos de conversão registrados nesta página.'},
    {'key': 'converted_sessions', 'label': 'Sessões que converteram', 'unit': 'count', 'source': 'Super Tag',
     'definition': 'Sessões que viram a página e tiveram qualquer conversão em qualquer página do site na mesma sessão.'},
    {'key': 'session_conversion_rate', 'label': 'Taxa de conversão da sessão', 'unit': 'percent', 'source': 'Super Tag',
     'definition': 'Sessões que converteram dividido por sessões da página. É associação, não prova de que a página causou a conversão.',
     'denominator': 'sessions'},
]


def pct(numerator, denominator):
    """Percent with one decimal, or None when there is nothing to divide by (never a fake zero)."""
    return round(100 * numerator / denominator, 1) if denominator else None


def device_bucket(width):
    if width is None:
        return 'unknown'
    return 'mobile' if width < 768 else 'tablet' if width < 1024 else 'desktop'


def build_metrics(counts, bounds):
    """Merge event counts and per-session bound totals into the dictionary's keys.

    ``counts`` comes from the event query, ``bounds`` is the sum over the session groups.
    Anything not measurable is None, so the screen can show "—" instead of 0.
    """
    sessions = int(counts.get('sessions') or 0)
    measured = int(counts.get('measured_visits') or 0)
    entrances = int(bounds.get('entrances') or 0)
    exits = int(bounds.get('exits') or 0)
    avg_ms, median_ms = counts.get('avg_active_ms'), counts.get('median_active_ms')
    metrics = {
        'sessions': sessions, 'visitors': int(counts.get('visitors') or 0), 'views': int(counts.get('views') or 0),
        'entrances': entrances, 'exits': exits, 'exit_rate': pct(exits, sessions),
        'single_page_rate': pct(int(bounds.get('single_page') or 0), entrances),
        'avg_active_seconds': round(float(avg_ms) / 1000, 1) if avg_ms is not None and measured else None,
        'median_active_seconds': round(float(median_ms) / 1000, 1) if median_ms is not None and measured else None,
        'clicks': int(counts.get('clicks') or 0),
        'clicks_per_session': round(int(counts.get('clicks') or 0) / sessions, 2) if sessions else None,
        'form_submits': int(counts.get('form_submits') or 0),
        'conversions_on_page': int(counts.get('conversions_on_page') or 0),
        'converted_sessions': int(bounds.get('converted') or 0),
        'session_conversion_rate': pct(int(bounds.get('converted') or 0), sessions),
    }
    for depth in (25, 50, 75, 100):
        metrics[f'scroll_{depth}'] = pct(int(counts.get(f'scroll_{depth}') or 0), sessions)
    metrics['measured_visits'] = measured
    metrics['reliable'] = sessions >= MIN_RELIABLE_SESSIONS
    return metrics


def compare(current, previous):
    """Absolute and relative change per numeric key; None when the previous window cannot support it."""
    if previous is None:
        return None
    delta = {}
    for key, value in current.items():
        before = previous.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or before is None:
            continue
        delta[key] = {'absolute': round(value - before, 2),
                      'relative': round(100 * (value - before) / before, 1) if before else None}
    return delta


def sum_groups(groups):
    totals = {'entrances': 0, 'exits': 0, 'single_page': 0, 'converted': 0, 'sessions': 0}
    for row in groups:
        for key in totals:
            totals[key] += int(row.get(key) or 0)
    return totals


def breakdown(groups, key_of, limit=None):
    """Sessions and conversions grouped by an arbitrary key of each group row."""
    grouped = {}
    for row in groups:
        entry = grouped.setdefault(key_of(row), {'sessions': 0, 'converted': 0})
        entry['sessions'] += int(row.get('sessions') or 0)
        entry['converted'] += int(row.get('converted') or 0)
    items = sorted(grouped.items(), key=lambda item: -item[1]['sessions'])
    return items[:limit] if limit else items


GRID_SIZE = 10
MIN_RELIABLE_CLICKS = 30
# 'handheld' = phones and tablets together (< 1024 px): the Celular view of Site & Jornada → Heatmap.
DEVICES = ('all', 'mobile', 'tablet', 'desktop', 'handheld')


def build_grid(rows):
    """10x10 matrix of click counts over the visible viewport at click time (x/y are per-mille of the viewport)."""
    cells = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    for row in rows:
        x, y = int(row['cx']), int(row['cy'])
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
            cells[y][x] += int(row['clicks'])
    peak = max((value for line in cells for value in line), default=0)
    return {'size': GRID_SIZE, 'cells': cells, 'peak': peak, 'total': sum(map(sum, cells))}


def build_elements(rows, page_sessions):
    """Ranking of marked elements. Click-per-exposure only exists where the element also reports visibility."""
    items = []
    for row in rows:
        clicks, click_sessions, seen = int(row['clicks']), int(row['click_sessions']), int(row['seen_sessions'])
        items.append({
            'element_id': row['element_id'], 'clicks': clicks, 'whatsapp_clicks': int(row['whatsapp_clicks']),
            'click_sessions': click_sessions, 'clicks_per_session': round(clicks / click_sessions, 2) if click_sessions else None,
            'share_of_sessions': pct(click_sessions, page_sessions),
            'seen_sessions': seen if seen else None,
            'click_rate_of_seen': pct(min(click_sessions, seen), seen) if seen else None,
        })
    return items


TOP_NEXT_PAGES = 6
CRM_STAGES = (('lead', 'Lead'), ('qualified', 'Lead qualificado'), ('sale', 'Venda'))


def build_conversion_map(rows, origin_label, crm_available):
    """Sankey data (origin -> page -> next step -> result) plus the CRM stage strip.

    Every link value is a count of sessions, and each column sums to the same total, so nothing is invented or lost.
    ``rows`` are grouped session rows: origin (platform key), kind (page|form|whatsapp|exit|active), next_path,
    converted, sessions, lead, qualified, sale.
    """
    total = sum(int(row['sessions']) for row in rows)
    page_totals = {}
    for row in rows:
        if row['kind'] == 'page':
            page_totals[row['next_path']] = page_totals.get(row['next_path'], 0) + int(row['sessions'])
    top = {path for path, _ in sorted(page_totals.items(), key=lambda item: -item[1])[:TOP_NEXT_PAGES]}
    labels = {'form': 'Enviou formulário', 'whatsapp': 'Clicou no WhatsApp', 'exit': 'Saiu do site', 'active': 'Sessão em andamento',
              'other': 'Outras páginas', 'yes': 'Converteu no site', 'no': 'Não converteu'}
    links, nodes = {}, {'page': {'id': 'page', 'column': 1, 'label': 'Esta página'}}

    def add(source, target, value):
        entry = links.setdefault((source, target), {'source': source, 'target': target, 'value': 0})
        entry['value'] += value

    def node(node_id, column, label):
        nodes.setdefault(node_id, {'id': node_id, 'column': column, 'label': label})

    crm = {key: 0 for key, _ in CRM_STAGES}
    for row in rows:
        sessions = int(row['sessions'])
        origin_id = f"o:{row['origin']}"
        node(origin_id, 0, origin_label(row['origin']))
        add(origin_id, 'page', sessions)
        if row['kind'] == 'page':
            next_id = f"n:page:{row['next_path']}" if row['next_path'] in top else 'n:other'
            node(next_id, 2, row['next_path'] if row['next_path'] in top else labels['other'])
        else:
            next_id = f"n:{row['kind']}"
            node(next_id, 2, labels[row['kind']])
        add('page', next_id, sessions)
        result_id = 'r:yes' if row['converted'] else 'r:no'
        node(result_id, 3, labels['yes' if row['converted'] else 'no'])
        add(next_id, result_id, sessions)
        for key, _ in CRM_STAGES:
            crm[key] += int(row.get(key) or 0)
    stages = [{'key': key, 'label': label, 'sessions': crm[key], 'rate': pct(crm[key], total)} for key, label in CRM_STAGES]
    return {'total': total, 'nodes': list(nodes.values()), 'links': list(links.values()),
            'crm': {'available': bool(crm_available), 'stages': stages if crm_available else []},
            'reliable': total >= MIN_RELIABLE_SESSIONS}


DOC_COLUMNS, DOC_ROWS = 10, 20


def build_document_grid(rows, document_clicks, all_clicks, median_height):
    """Whole-page heat in proportional bands (10 columns x 20 rows of the document), from contract-v2 clicks only.

    ``coverage`` says how many of the page's clicks carry a document position; older cached tags do not, and the
    screen must say so instead of presenting a partial picture as complete.
    """
    cells = [[0] * DOC_COLUMNS for _ in range(DOC_ROWS)]
    for row in rows:
        x, y = int(row['cx']), int(row['cy'])
        if 0 <= x < DOC_COLUMNS and 0 <= y < DOC_ROWS:
            cells[y][x] += int(row['clicks'])
    peak = max((value for line in cells for value in line), default=0)
    return {'columns': DOC_COLUMNS, 'rows': DOC_ROWS, 'cells': cells, 'peak': peak, 'total': sum(map(sum, cells)),
            'coverage': pct(int(document_clicks), int(all_clicks)), 'median_height': int(median_height) if median_height else None}
